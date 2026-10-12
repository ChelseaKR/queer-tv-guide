package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.JsonEdit.editArray
import com.chelseakr.queertvguide.core.JsonEdit.editObject
import com.chelseakr.queertvguide.core.JsonEdit.str
import com.chelseakr.queertvguide.core.JsonEdit.with
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/**
 * Same inputs, same outputs as GuideCore (DECISIONS 0018): reads
 * `ios/GuideCore/Tests/Fixtures/parity.golden.json`, which GuideCore's own
 * `ParityGoldenTests` rebuilds and checks on every `swift test`, recomputes
 * every case with the Kotlin port, and fails on any difference: a reminder
 * set at another instant or worded differently, a next-episode sentence in
 * another time zone's wall clock, a widget line, an absence's wording, a
 * search hit, a filter, or a backup file's bytes.
 */
class ParityGoldenTest {
    private val golden: JsonObject = Json.parseToJsonElement(Repo.goldenFile.readText()).jsonObject
    private val mismatches = mutableListOf<String>()

    private fun text(zone: String) = DateText(Locale.US, ZoneId.of(zone))

    private fun check(path: String, expected: Any?, actual: Any?) {
        if (expected != actual) mismatches += "$path\n    GuideCore: $expected\n    Android:   $actual"
    }

    private fun JsonElement.s(): String? = if (this is JsonNull) null else jsonPrimitive.content
    private fun JsonElement.strings(): List<String> = jsonArray.map { it.jsonPrimitive.content }

    private fun finish() {
        assertTrue(
            "Android says something GuideCore does not (${mismatches.size} differences):\n" + mismatches.take(40).joinToString("\n"),
            mismatches.isEmpty(),
        )
    }

    @Test
    fun theGoldenFileIsTheOneThisTestExpects() {
        assertEquals("queer-frame-parity", golden["format"]!!.s())
        assertEquals(1, golden["version"]!!.jsonPrimitive.int)
        assertEquals("en_US", golden["locale"]!!.s())
        // Denominators: a golden file emptied by accident must not pass.
        assertEquals(8, golden["variants"]!!.jsonArray.size)
        assertEquals(5, golden["zones"]!!.jsonArray.size)
        assertTrue(golden["search"]!!.jsonObject["queries"]!!.jsonArray.size >= 20)
    }

    private fun variantSnapshot(variant: JsonObject): Snapshot {
        val edit = variant["edit"]!!.jsonObject
        var root = Repo.fixtureJson().editArray("shows", 0) { show ->
            show.editObject("schedule") { schedule ->
                schedule.editObject("next_episode") { episode ->
                    episode.with("airstamp", edit["airstamp"]!!).with("airdate", edit["airdate"]!!).with("airtime", edit["airtime"]!!)
                }
            }
        }
        variant["night_shift_edit"]?.jsonObject?.let { night ->
            root = root.editArray("shows", 3) { show ->
                show.editObject("schedule") { schedule ->
                    schedule.with(
                        "next_episode",
                        JsonObject(
                            mapOf(
                                "tvmaze_id" to JsonPrimitive(900104), "season" to JsonPrimitive(2), "number" to JsonPrimitive(1),
                                "name" to JsonPrimitive("Static"), "airdate" to night["airdate"]!!, "airtime" to night["airtime"]!!,
                                "airstamp" to night["airstamp"]!!, "runtime" to JsonPrimitive(30),
                                "url" to JsonPrimitive("https://www.tvmaze.com/episodes/900104/night-shift-radio-2x01-static"),
                            ),
                        ),
                    )
                }
            }
        }
        val snapshot = SnapshotDecoder.decode(Repo.bytes(root))
        // The edit landed: a sabotage that silently did nothing would read as a pass.
        val episode = snapshot.shows[0].schedule.nextEpisode!!
        assertEquals(edit["airstamp"]!!.s(), episode.airstamp)
        assertEquals(edit["airdate"]!!.s(), episode.airdate)
        assertEquals(edit["airtime"]!!.s(), episode.airtime)
        return snapshot
    }

    @Test
    fun remindersNextEpisodesAndTheWidgetMatchInEveryZone() {
        val favorites = golden["favorites"]!!.strings()
        var reminderCount = 0
        for (v in golden["variants"]!!.jsonArray) {
            val variant = v.jsonObject
            val name = variant["name"]!!.s()
            val snapshot = variantSnapshot(variant)
            for ((zone, byClock) in variant["by_zone"]!!.jsonObject) {
                val dateText = text(zone)
                for ((clock, case) in byClock.jsonObject) {
                    val now = Instant.parse(clock)
                    val plan = EpisodeReminders.plan(favorites, snapshot, now, dateText)
                    val expected = case.jsonObject["reminders"]!!.jsonArray.map { it.jsonObject }
                    check("$name/$zone/$clock reminder count", expected.size, plan.size)
                    expected.zip(plan).forEachIndexed { i, (e, p) ->
                        val at = "$name/$zone/$clock reminder $i"
                        check("$at identifier", e["identifier"]!!.s(), p.identifier)
                        check("$at show", e["show_id"]!!.s(), p.showId)
                        check("$at fire instant", e["fire_at"]!!.s(), Dates.formatInstant(p.fireAt))
                        check("$at title", e["title"]!!.s(), p.title)
                        check("$at body", e["body"]!!.s(), p.body)
                        reminderCount += 1
                    }
                    for ((showId, sentence) in case.jsonObject["next_episode"]!!.jsonObject) {
                        val show = snapshot.show(showId)!!
                        check("$name/$zone/$clock next episode $showId", sentence.s(), Presentation.nextEpisode(show.schedule, now, dateText))
                    }
                }
            }
            val widget = variant["widget"]!!.jsonObject
            val upNext = UpNext.build(favorites, snapshot)
            check("$name widget missing", widget["missing_show_count"]!!.jsonPrimitive.int, upNext.missingShowCount)
            val items = widget["items"]!!.jsonArray.map { it.jsonObject }
            check("$name widget item count", items.size, upNext.items.size)
            items.zip(upNext.items).forEach { (e, item) ->
                check("$name widget item ${item.showId}", listOf(e["show_id"]!!.s(), e["title"]!!.s(), e["status"]!!.s(), e["season"]!!.s(), e["number"]!!.s(), e["airdate"]!!.s()), listOf(item.showId, item.title, item.status.raw, item.season?.toString(), item.number?.toString(), item.airdate))
            }
            for ((clock, case) in widget["by_clock"]!!.jsonObject) {
                val today = Instant.parse(clock)
                val ordered = upNext.ordered(today)
                val us = text("UTC")
                check("$name widget order $clock", case.jsonObject["ordered"]!!.strings(), ordered.map { it.showId })
                check("$name widget lines $clock", case.jsonObject["lines"]!!.strings(), ordered.map { UpNextPresentation.line(it, today, us) })
                check("$name widget spoken $clock", case.jsonObject["spoken"]!!.strings(), ordered.map { UpNextPresentation.spoken(it, today, us) })
            }
        }
        // Denominator: the variants plan reminders in every zone.
        assertTrue("only $reminderCount reminders compared", reminderCount >= 60)
        finish()
    }

    @Test
    fun everyAbsenceAndEveryShowReadsTheSame() {
        val s = Repo.fixture()
        val p = golden["presentation"]!!.jsonObject
        val index = SearchIndex(s)
        val utc = text("UTC")
        for ((id, e) in p["shows"]!!.jsonObject) {
            val show = s.show(id)!!
            val o = e.jsonObject
            val cast = s.charactersInShow(id)
            val deaths = Presentation.showDeaths(cast, show)
            check("$id years", o["years"]!!.s(), Presentation.years(show.years))
            check("$id seasons", o["seasons"]!!.s(), Presentation.seasons(show.seasons))
            check("$id worth it", o["worth_it"]!!.s(), Presentation.worthIt(show.ratings.worthIt))
            check("$id quality", o["quality"]!!.s(), Presentation.ratingValue(show.ratings.quality))
            check("$id realness", o["realness"]!!.s(), Presentation.ratingValue(show.ratings.realness))
            check("$id screentime", o["screentime"]!!.s(), Presentation.ratingValue(show.ratings.screentime))
            check("$id rating", o["rating_quality"]!!.s(), Presentation.rating(show.ratings.quality, "Quality"))
            check("$id score", o["score"]!!.s(), Presentation.score(show.ratings.score))
            val d = o["deaths"]!!.jsonObject
            check("$id deaths headline", d["headline"]!!.s(), deaths.headline)
            check("$id deaths lines", d["lines"]!!.strings(), deaths.lines)
            check("$id deaths notes", d["notes"]!!.strings(), deaths.notes)
            check("$id deaths spoken", d["spoken"]!!.s(), deaths.spoken)
            check("$id deaths summary", o["deaths_summary"]!!.s(), Presentation.deathsSummary(cast))
            check("$id tropes shown", o["tropes_shown"]!!.s(), Presentation.terms(Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs), Presentation.NO_TROPES))
            check("$id triggers", o["triggers"]!!.s(), Presentation.terms(show.triggers, Presentation.NO_TRIGGERS))
            val links = o["watch_links"]!!.jsonArray.map { it.jsonObject }
            check("$id watch link count", links.size, show.watchLinks.size)
            links.zip(show.watchLinks).forEach { (l, link) ->
                check("$id watch label", l["label"]!!.s(), Presentation.watchLinkLabel(link, show.networks))
                check("$id display host", l["display_host"]!!.s(), Presentation.displayHost(link.host))
            }
            val credit = Attribution.tvmazeCredit(show.schedule, s)
            val expectedCredit = o["tvmaze_credit"]!!
            if (expectedCredit is JsonNull) {
                check("$id tvmaze credit", null, credit)
            } else {
                val c = expectedCredit.jsonObject
                check("$id tvmaze credit", listOf(c["source_title"]!!.s(), c["source_url"]!!.s(), c["license_title"]!!.s(), c["license_url"]!!.s(), c["spoken"]!!.s()), credit?.let { listOf(it.source.title, it.source.url, it.license.title, it.license.url, it.spoken) })
            }
            check("$id lezwatch label", o["lezwatch_link_label"]!!.s(), Attribution.lezWatchLinkLabel(show.title))
            check("$id share url", o["share_url"]!!.s(), Sharing.cleanUrl(show.sourceUrl))
            val cov = o["death_coverage"]!!.jsonObject
            val coverage = index.deathCoverage(show)
            check("$id death coverage", listOf(cov["has_characters"]!!.jsonPrimitive.booleanOrNull, cov["any_recorded_death"]!!.jsonPrimitive.booleanOrNull), listOf(coverage.hasCharacters, coverage.anyRecordedDeath))
        }
        for ((id, e) in p["characters"]!!.jsonObject) {
            val c = s.character(id)!!
            val o = e.jsonObject
            check("$id death", o["death"]!!.s(), Presentation.death(c.death, c.name))
            check("$id death short", o["death_short"]!!.s(), Presentation.deathShort(c.death))
            check("$id tropes shown", o["tropes_shown"]!!.strings(), Presentation.withoutSpoilers(c.cliches, Presentation.deathSpoilerClicheSlugs).map { it.name })
        }
        for (y in p["years"]!!.jsonArray.map { it.jsonObject }) {
            val years = Years(y["start"]!!.s()?.toInt(), y["end"]!!.s()?.toInt(), OnAir.valueOf(y["on_air"]!!.s()!!.uppercase()))
            check("years $years", y["text"]!!.s(), Presentation.years(years))
        }
        for (n in p["seasons"]!!.jsonArray.map { it.jsonObject }) {
            check("seasons ${n["n"]}", n["text"]!!.s(), Presentation.seasons(n["n"]!!.s()?.toInt()))
        }
        for (a in p["ages"]!!.jsonArray.map { it.jsonObject }) {
            check("age ${a["seconds"]}", a["text"]!!.s(), Presentation.age(a["seconds"]!!.jsonPrimitive.long))
        }
        for (a in p["spans"]!!.jsonArray.map { it.jsonObject }) {
            check("span ${a["seconds"]}", a["text"]!!.s(), Presentation.span(a["seconds"]!!.jsonPrimitive.long))
        }
        check("return refresh rule", p["return_refresh_rule"]!!.s(), Presentation.returnRefreshRule)
        for (i in p["import_summaries"]!!.jsonArray.map { it.jsonObject }) {
            val n = listOf("added", "already_saved", "not_in_snapshot", "unreadable").map { i[it]!!.jsonPrimitive.int }
            check("import summary $n", i["text"]!!.s(), Presentation.importSummary(n[0], n[1], n[2], n[3]))
        }
        check("no watch links", p["no_watch_links"]!!.s(), Presentation.NO_WATCH_LINKS)
        check("no characters", p["no_characters"]!!.s(), Presentation.NO_CHARACTERS)
        check("non-endorsement", p["non_endorsement"]!!.s(), Attribution.NON_ENDORSEMENT)
        val general = p["tvmaze_general_credit"]!!.jsonObject
        val credit = Attribution.tvmazeCredit(s)!!
        check("general tvmaze credit", listOf(general["source_title"]!!.s(), general["source_url"]!!.s(), general["license_title"]!!.s(), general["license_url"]!!.s()), listOf(credit.source.title, credit.source.url, credit.license.title, credit.license.url))
        for (m in p["widget_more"]!!.jsonArray.map { it.jsonObject }) {
            check("widget more $m", m["text"]!!.s(), UpNextPresentation.more(m["count"]!!.jsonPrimitive.int, m["missing"]!!.jsonPrimitive.int))
        }
        check("date-only next episode in UTC", true, utc.mediumDay(java.time.LocalDate.of(2026, 9, 20)) == "Sep 20, 2026")
        finish()
    }

    @Test
    fun freshnessWordingAndTheReturnRefreshGateMatch() {
        val s = Repo.fixture()
        val cases = golden["freshness"]!!.jsonArray.map { it.jsonObject }
        assertEquals(65, cases.size)
        for (c in cases) {
            val zone = c["zone"]!!.s()!!
            val offset = c["offset_seconds"]!!.jsonPrimitive.long
            val now = s.generatedAt.plusSeconds(offset)
            val dateText = text(zone)
            val freshness = DataFreshness.assess(s.generatedAt, now)
            val at = "$zone offset $offset"
            val state = when (freshness) {
                is DataFreshness.Current -> "current"
                is DataFreshness.Stale -> "stale"
                DataFreshness.Unknown -> "unknown"
            }
            check("$at state", c["state"]!!.s(), state)
            check("$at data as of", c["data_as_of"]!!.s(), Presentation.dataAsOf(s.generatedAt, freshness, dateText))
            val warning = Presentation.freshnessWarning(s.generatedAt, freshness, dateText)
            val expected = c["warning"]!!
            if (expected is JsonNull) {
                check("$at warning", null, warning)
            } else {
                val w = expected.jsonObject
                check("$at warning", listOf(w["title"]!!.s(), w["detail"]!!.s(), w["spoken"]!!.s()), warning?.let { listOf(it.title, it.detail, it.spoken) })
            }
            check("$at widget age", c["widget_age"]!!.s(), UpNextPresentation.dataAge(s.generatedAt, now, dateText))
            val gate = ForegroundRefreshGate()
            val got = listOf(
                gate.shouldRefresh(s.generatedAt, now),
                gate.shouldRefresh(s.generatedAt, now.plusSeconds(3600)),
                gate.shouldRefresh(s.generatedAt, now.plusSeconds(6 * 3600)),
            )
            check("$at return refresh", c["return_refresh"]!!.jsonArray.map { it.jsonPrimitive.booleanOrNull }, got)
        }
        finish()
    }

    @Test
    fun searchHitsFiltersAndFoldingMatch() {
        val s = Repo.fixture()
        val index = SearchIndex(s)
        val search = golden["search"]!!.jsonObject
        for (q in search["queries"]!!.jsonArray.map { it.jsonObject }) {
            val query = q["query"]!!.s()!!
            val r = index.search(query)
            check("'$query' hits", q["hits"]!!.strings(), r.hits.map { it.id })
            check("'$query' total", q["total"]!!.jsonPrimitive.int, r.totalCount)
            check("'$query' no recorded deaths", q["no_recorded_deaths_hits"]!!.strings(), index.search(query, SearchIndex.Filters(noRecordedDeaths = true)).hits.map { it.id })
            val capped = index.search(query, limit = 2)
            check("'$query' limit 2", q["limit_2_hits"]!!.strings(), capped.hits.map { it.id })
            check("'$query' limit 2 total", q["limit_2_total"]!!.jsonPrimitive.int, capped.totalCount)
        }
        val filterSets = mapOf(
            "none" to SearchIndex.Filters(),
            "no_recorded_deaths" to SearchIndex.Filters(noRecordedDeaths = true),
            "worth_it_yes" to SearchIndex.Filters(worthIt = setOf(WorthIt.YES)),
            "worth_it_yes_meh" to SearchIndex.Filters(worthIt = setOf(WorthIt.YES, WorthIt.MEH)),
            "worth_it_tbd" to SearchIndex.Filters(worthIt = setOf(WorthIt.TBD)),
            "has_watch_link" to SearchIndex.Filters(hasWatchLink = true),
            "host_example_com" to SearchIndex.Filters(watchHosts = setOf("example.com")),
            "host_store_example_org" to SearchIndex.Filters(watchHosts = setOf("store.example.org")),
            "trope_slow_burn" to SearchIndex.Filters(tropes = setOf("slow-burn")),
            "hide_violence" to SearchIndex.Filters(hiddenTriggerWarnings = setOf("violence")),
            "all" to SearchIndex.Filters(setOf(WorthIt.YES, WorthIt.NO), true, true, setOf("example.com"), setOf("slow-burn"), setOf("violence")),
        )
        val browse = search["browse"]!!.jsonArray.map { it.jsonObject }
        assertEquals(filterSets.keys.toList(), browse.map { it["name"]!!.s() })
        for (b in browse) {
            val name = b["name"]!!.s()!!
            val filters = filterSets.getValue(name)
            check("$name active count", b["active_count"]!!.jsonPrimitive.int, filters.activeCount)
            check("$name browse", b["shows"]!!.strings(), index.browse(filters).map { it.id })
            check("$name harbor", b["harbor_hits"]!!.strings(), index.search("harbor", filters).hits.map { it.id })
            check("$name example", b["example_hits"]!!.strings(), index.search("example", filters).hits.map { it.id })
        }
        val options = search["filter_options"]!!.jsonObject
        check("watch hosts", options["watch_hosts"]!!.jsonArray.map { it.jsonObject["key"]!!.s() to it.jsonObject["show_count"]!!.jsonPrimitive.int }, index.filterOptions.watchHosts.map { it.key to it.showCount })
        check("tropes", options["tropes"]!!.jsonArray.map { Triple(it.jsonObject["slug"]!!.s(), it.jsonObject["name"]!!.s(), it.jsonObject["show_count"]!!.jsonPrimitive.int) }, index.filterOptions.tropes.map { Triple(it.slug, it.name, it.showCount) })
        check("triggers", options["trigger_warnings"]!!.jsonArray.map { Triple(it.jsonObject["slug"]!!.s(), it.jsonObject["name"]!!.s(), it.jsonObject["show_count"]!!.jsonPrimitive.int) }, index.filterOptions.triggerWarnings.map { Triple(it.slug, it.name, it.showCount) })
        for (f in search["folds"]!!.jsonArray.map { it.jsonObject }) {
            check("fold '${f["text"]!!.s()}'", f["folded"]!!.s(), SearchIndex.fold(f["text"]!!.s()!!))
        }
        for (h in search["watch_host_keys"]!!.jsonArray.map { it.jsonObject }) {
            check("host key ${h["host"]!!.s()}", h["key"]!!.s(), SearchIndex.WatchHost.key(h["host"]!!.s()!!))
        }
        finish()
    }

    @Test
    fun aBackupFileIsTheSameBytesOnBothPlatforms() {
        val backup = golden["backup"]!!.jsonObject
        val entries = backup["entries"]!!.jsonArray.map {
            val o = it.jsonObject
            FavoritesStore.Entry(FavoritesStore.Kind.from(o["kind"]!!.s())!!, o["id"]!!.s()!!, Instant.parse(o["added_at"]!!.s()))
        }
        check("export", backup["export"]!!.s(), String(FavoritesBackup.export(entries), Charsets.UTF_8))
        check("export empty", backup["export_empty"]!!.s(), String(FavoritesBackup.export(emptyList()), Charsets.UTF_8))
        // And the iOS file imports here, entry for entry.
        val parsed = FavoritesBackup.parse(backup["export"]!!.s()!!.toByteArray(), Instant.parse("2026-10-01T00:00:00Z")) { _, _ -> true }
        check("import of the iOS export", entries, parsed.entries)
        for (w in backup["well_formed"]!!.jsonArray.map { it.jsonObject }) {
            val id = w["id"]!!.s()!!
            check("well formed $id as show", w["as_show"]!!.jsonPrimitive.booleanOrNull, FavoritesBackup.isWellFormed(id, FavoritesStore.Kind.SHOW))
            check("well formed $id as character", w["as_character"]!!.jsonPrimitive.booleanOrNull, FavoritesBackup.isWellFormed(id, FavoritesStore.Kind.CHARACTER))
        }
        finish()
    }

    /**
     * The negative control: the comparison above can fail. One word changed
     * in what Android says, and the reminder case reports a difference.
     */
    @Test
    fun theComparisonCanFail() {
        val variant = golden["variants"]!!.jsonArray[0].jsonObject
        val case = variant["by_zone"]!!.jsonObject["UTC"]!!.jsonObject["2026-09-14T00:00:00Z"]!!.jsonObject
        val expected = case["reminders"]!!.jsonArray[0].jsonObject["body"]!!.s()
        val plan = EpisodeReminders.plan(golden["favorites"]!!.strings(), variantSnapshot(variant), Instant.parse("2026-09-14T00:00:00Z"), text("UTC"))
        assertEquals(expected, plan[0].body)
        check("sabotaged body", expected, plan[0].body.replace("TVmaze", "TV maze"))
        assertEquals(1, mismatches.size)
        // And the same reminder planned in the wrong zone fires at a different instant.
        val placeholder = golden["variants"]!!.jsonArray.first { it.jsonObject["name"]!!.s() == "placeholder-stamp" }.jsonObject
        val tokyo = placeholder["by_zone"]!!.jsonObject["Asia/Tokyo"]!!.jsonObject["2026-09-14T00:00:00Z"]!!.jsonObject["reminders"]!!.jsonArray[0].jsonObject
        val inLosAngeles = EpisodeReminders.plan(golden["favorites"]!!.strings(), variantSnapshot(placeholder), Instant.parse("2026-09-14T00:00:00Z"), text("America/Los_Angeles"))
        assertTrue(tokyo["fire_at"]!!.s() != Dates.formatInstant(inLosAngeles[0].fireAt))
    }
}
