package com.chelseakr.queertvguide.core

import java.text.Normalizer
import java.util.Locale

/**
 * Local, case- and diacritic-insensitive search over shows and characters:
 * GuideCore's `SearchIndex`, ported. Punctuation need not be typed ("greys
 * anatomy" finds "Grey’s Anatomy"), and a query's words can come in any
 * order. Built once per snapshot; queried per keystroke; no network.
 */
class SearchIndex(private val snapshot: Snapshot) {
    data class SearchResults(val hits: List<Hit>, val totalCount: Int) {
        val isCapped: Boolean get() = totalCount > hits.size
    }

    sealed class Hit {
        abstract val id: String

        data class ShowHit(val show: Show) : Hit() {
            override val id: String get() = "show:${show.id}"
        }

        data class CharacterHit(val character: Character) : Hit() {
            override val id: String get() = "character:${character.id}"
        }
    }

    data class Filters(
        /** Only shows whose worth-it verdict is one of these. Empty: no filter. */
        val worthIt: Set<WorthIt> = emptySet(),
        /** Only shows whose listed characters have no recorded death; a show with no listed characters does not pass. */
        val noRecordedDeaths: Boolean = false,
        val hasWatchLink: Boolean = false,
        /** Only shows with a link on one of these hosts ([WatchHost.key]). */
        val watchHosts: Set<String> = emptySet(),
        /** Only shows tagged with at least one of these trope slugs. */
        val tropes: Set<String> = emptySet(),
        /** Leaves out shows whose trigger warning is one of these levels; "none listed" is kept. */
        val hiddenTriggerWarnings: Set<String> = emptySet(),
    ) {
        val isEmpty: Boolean get() = activeCount == 0
        val activeCount: Int
            get() = worthIt.size + (if (noRecordedDeaths) 1 else 0) + (if (hasWatchLink) 1 else 0) +
                watchHosts.size + tropes.size + hiddenTriggerWarnings.size
    }

    data class WatchHost(val key: String, val showCount: Int) {
        companion object {
            fun key(host: String): String {
                val lower = host.lowercase(Locale.ROOT)
                return if (lower.startsWith("www.")) lower.drop(4) else lower
            }
        }
    }

    data class FilterTerm(val slug: String, val name: String, val showCount: Int)

    data class FilterOptions(
        /** Most shows first, then by name. */
        val watchHosts: List<WatchHost>,
        /** Alphabetical; death-revealing tropes are left out. */
        val tropes: List<FilterTerm>,
        /** Low, Medium, High, then any other level in the snapshot's order. */
        val triggerWarnings: List<FilterTerm>,
    )

    private class Entry(
        val hit: Hit,
        val primary: String,
        val primaryWords: List<String>,
        val primaryCompact: String,
        val secondary: List<String>,
        val secondaryWords: List<String>,
    )

    private val entries: List<Entry>
    private val showsByTitle: List<Show>
    private val watchHostKeysByShow: Map<String, Set<String>>
    val filterOptions: FilterOptions

    init {
        val list = ArrayList<Entry>(snapshot.shows.size + snapshot.characters.size)
        for (show in snapshot.shows) {
            list += entry(Hit.ShowHit(show), show.title, show.alternateNames + show.networks.map { it.name })
        }
        for (character in snapshot.characters) {
            val showTitles = character.shows.mapNotNull { snapshot.show(it.showId)?.title }
            val actorNames = character.actors.mapNotNull { it.name }
            list += entry(Hit.CharacterHit(character), character.name, actorNames + showTitles)
        }
        entries = list
        showsByTitle = snapshot.shows.map { fold(it.title) to it }.sortedWith { a, b -> compareSwift(a.first, b.first) }.map { it.second }

        val hostKeys = HashMap<String, Set<String>>()
        val hostCounts = HashMap<String, Int>()
        val tropeCounts = HashMap<String, Int>()
        val triggerCounts = HashMap<String, Int>()
        for (show in snapshot.shows) {
            val keys = show.watchLinks.map { WatchHost.key(it.host) }.toSet()
            hostKeys[show.id] = keys
            for (key in keys) hostCounts[key] = (hostCounts[key] ?: 0) + 1
            for (slug in show.tropes.map { it.slug }.toSet()) tropeCounts[slug] = (tropeCounts[slug] ?: 0) + 1
            for (slug in show.triggers.map { it.slug }.toSet()) triggerCounts[slug] = (triggerCounts[slug] ?: 0) + 1
        }
        watchHostKeysByShow = hostKeys
        val hosts = hostCounts.map { WatchHost(it.key, it.value) }
            .sortedWith { a, b -> if (a.showCount != b.showCount) b.showCount - a.showCount else compareSwift(a.key, b.key) }
        val tropes = snapshot.taxonomies.tropes
            .filter { it.slug !in Presentation.deathSpoilerTropeSlugs && (tropeCounts[it.slug] ?: 0) > 0 }
            .map { FilterTerm(it.slug, it.name, tropeCounts[it.slug] ?: 0) }
            .sortedWith { a, b -> compareSwift(fold(a.name), fold(b.name)) }
        val severity = mapOf("low" to 0, "medium" to 1, "high" to 2)
        val triggers = snapshot.taxonomies.triggers
            .filter { (triggerCounts[it.slug] ?: 0) > 0 }
            .map { FilterTerm(it.slug, it.name, triggerCounts[it.slug] ?: 0) }
            .withIndex()
            .sortedWith(compareBy<IndexedValue<FilterTerm>>({ severity[it.value.slug] ?: 3 }, { it.index }))
            .map { it.value }
        filterOptions = FilterOptions(hosts, tropes, triggers)
    }

    /** Empty or whitespace-only queries return nothing: the screen browses instead. */
    fun search(query: String, filters: Filters = Filters(), limit: Int = 50): SearchResults {
        val q = fold(query)
        if (q.isEmpty()) return SearchResults(emptyList(), 0)
        val parsed = Query(q, words(q), q.replace(" ", ""))
        val scored = ArrayList<Triple<Int, Int, Hit>>()
        entries.forEachIndexed { order, entry ->
            val score = score(entry, parsed) ?: return@forEachIndexed
            if (!passes(entry.hit, filters)) return@forEachIndexed
            scored += Triple(score, order, entry.hit)
        }
        scored.sortWith { a, b -> if (a.first != b.first) b.first - a.first else a.second - b.second }
        return SearchResults(scored.take(limit).map { it.third }, scored.size)
    }

    /** All shows that pass the filters, alphabetical: browsing with an empty query. */
    fun browse(filters: Filters): List<Show> = showsByTitle.filter { passes(Hit.ShowHit(it), filters) }

    data class DeathCoverage(val hasCharacters: Boolean, val anyRecordedDeath: Boolean)

    /** Whether any listed character has a recorded death, alongside whether any is listed at all. */
    fun deathCoverage(show: Show): DeathCoverage {
        val cast = snapshot.charactersInShow(show.id)
        return DeathCoverage(cast.isNotEmpty(), cast.any { it.death.isRecorded })
    }

    private fun passes(hit: Hit, filters: Filters): Boolean {
        if (filters.isEmpty) return true
        return when (hit) {
            is Hit.CharacterHit -> hit.character.shows.mapNotNull { snapshot.show(it.showId) }.any { passes(Hit.ShowHit(it), filters) }
            is Hit.ShowHit -> {
                val show = hit.show
                if (filters.worthIt.isNotEmpty()) {
                    val w = show.ratings.worthItKnown
                    if (w == null || w !in filters.worthIt) return false
                }
                if (filters.hasWatchLink && show.watchLinks.isEmpty()) return false
                if (filters.watchHosts.isNotEmpty()) {
                    val keys = watchHostKeysByShow[show.id] ?: return false
                    if (keys.none { it in filters.watchHosts }) return false
                }
                if (filters.tropes.isNotEmpty() && show.tropes.none { it.slug in filters.tropes }) return false
                if (filters.hiddenTriggerWarnings.isNotEmpty() && show.triggers.any { it.slug in filters.hiddenTriggerWarnings }) return false
                if (filters.noRecordedDeaths) {
                    val coverage = deathCoverage(show)
                    if (!coverage.hasCharacters || coverage.anyRecordedDeath) return false
                }
                true
            }
        }
    }

    private class Query(val text: String, val words: List<String>, val compact: String)

    companion object {
        private fun entry(hit: Hit, primary: String, secondary: List<String>): Entry {
            val folded = fold(primary)
            val foldedSecondary = secondary.map { fold(it) }
            return Entry(hit, folded, words(folded), folded.replace(" ", ""), foldedSecondary, foldedSecondary.flatMap { words(it) })
        }

        /**
         * Higher is better; null is no match. Whole title, title prefix, every
         * query word starting a title word, the query inside the title, then
         * the same against actors, networks and show titles.
         */
        private fun score(entry: Entry, q: Query): Int? = when {
            entry.primary == q.text -> 100
            entry.primary.startsWith(q.text) -> 80
            allWordsStart(q.words, entry.primaryWords) -> 60
            entry.primary.contains(q.text) || (q.compact.isNotEmpty() && entry.primaryCompact.contains(q.compact)) -> 40
            entry.secondary.any { it.startsWith(q.text) } -> 30
            allWordsStart(q.words, entry.primaryWords, entry.secondaryWords) -> 25
            entry.secondary.any { it.contains(q.text) } -> 20
            else -> null
        }

        private fun allWordsStart(queryWords: List<String>, words: List<String>, more: List<String> = emptyList()): Boolean {
            if (queryWords.isEmpty()) return false
            return queryWords.all { q -> words.any { it.startsWith(q) } || more.any { it.startsWith(q) } }
        }

        private fun words(folded: String): List<String> = folded.split(' ').filter { it.isNotEmpty() }

        private val apostrophes = setOf('\'', '’', '‘', 'ʼ', '`', '´')

        /**
         * Case, diacritics and width folded; "&" read as "and"; apostrophes
         * dropped ("Grey’s" is "greys"); every other punctuation mark a space.
         */
        fun fold(s: String): String {
            // NFKD splits accents off their letters and maps full-width forms
            // to ASCII; the marks are then dropped.
            val decomposed = Normalizer.normalize(s, Normalizer.Form.NFKD)
            val out = StringBuilder(decomposed.length)
            for (c in decomposed) {
                when {
                    c.category == CharCategory.NON_SPACING_MARK || c.category == CharCategory.ENCLOSING_MARK ||
                        c.category == CharCategory.COMBINING_SPACING_MARK -> Unit
                    c == '&' -> out.append(" and ")
                    c in apostrophes -> Unit
                    c.isLetterOrDigit() || c.category == CharCategory.LETTER_NUMBER || c.category == CharCategory.OTHER_NUMBER -> out.append(c)
                    else -> out.append(' ')
                }
            }
            return out.toString().lowercase(Locale.ROOT).split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        }

        /** Swift's `String <` on folded text: Unicode scalar order. */
        internal fun compareSwift(a: String, b: String): Int {
            val ia = a.codePoints().iterator()
            val ib = b.codePoints().iterator()
            while (ia.hasNext() && ib.hasNext()) {
                val x = ia.nextInt()
                val y = ib.nextInt()
                if (x != y) return x.compareTo(y)
            }
            return ia.hasNext().compareTo(ib.hasNext())
        }
    }
}
