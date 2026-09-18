# Data sources, licences, attribution

Every source: the licence as published by the source (quoted, dated, linked),
what it permits for a paid app that bundles a derived dataset, the attribution
text the app must show and where, and any share-alike obligation on the derived
snapshot. Plain-text copies of every page quoted here, as read, are in
`docs/terms-snapshots/2026-09-13/` with checksums; keep them for App Review
5.2.2 ("Authorization must be provided upon request"). The bytes are kept
exactly as fetched (`.gitattributes` marks the directory `-text`; LezWatch
serves robots.txt with CRLF line endings) and CI re-verifies every
`SHA256SUMS` (`pipeline/tests/test_terms_snapshots.py`).

Rule: if any source's terms cannot be read today, it is **unknown** and is not
used until it can be. Nobody is contacted to ask, with one owner-decided
exception: LezWatch.TV, asked in writing before the app ships (DECISIONS
0008, [moved to private strategy notes]).

## Summary table

| Source | What we take | Licence (verbatim, link, date read) | Paid-app bundling OK? | Attribution required | Share-alike on the snapshot? |
|---|---|---|---|---|---|
| LezWatch.TV REST API | shows, characters, deaths, worth-it/quality/realness/screentime, tropes/clichés, gender/sexuality/romantic terms, where-to-watch URLs, actor names. **No images.** | Terms of Use, "Last Updated: 16 August 2018", https://lezwatchtv.com/tos/, read 2026-09-13: *"You are welcome to use, reuse, and extend the data here for no fees. … We do ask you link back to us, or note us by name, as a thank you in your final works."* API docs, https://docs.lezwatchtv.com/api/, read 2026-09-13: *"The public API at LezWatchTV is available for anyone anywhere to consume and reproduce the data found on this site."* | **Pending LezWatch.TV's written OK: the app does not ship without it** (DECISIONS 0008). The terms read as yes ("for no fees" with no non-commercial limit; the API docs say "anyone anywhere"), but the same page scopes the service to displaying data "on your own site", so the owner is asking rather than relying on a reading. Request drafted, not yet sent. Data only: the ToS disclaims copyright in images ("believe them to fall under the fair-use clause"), which does not transfer to us, so the pipeline takes no image and the snapshot has no image field. | Yes, as a request, not a licence condition: *"link back to us, or note us by name"*. The app names LezWatch.TV with a link on the attribution screen and links every show and character to its LezWatch page (`source_url`). | **None imposed.** LezWatch attaches no licence to derived works. Its data may sit inside the BY-SA snapshot. |
| TVmaze API | per show: TVmaze id/URL, status, premiered/ended, network/web channel, next and previous episode (season, number, name, air date/time, runtime, URL). **No images, no summaries.** | https://www.tvmaze.com/api §Licensing, read 2026-09-13: *"Use of the TVmaze API is licensed by CC BY-SA. This means the data can freely be used for any purpose, as long as TVmaze is properly credited as source and your usage complies with the ShareAlike provision. You can satisfy the attribution requirement by linking back to TVmaze from within your application or website, for example using the URLs available in the API."* The "CC BY-SA" link targets `http://creativecommons.org/licenses/by-sa/4.0/`. Licence text: https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt, read 2026-09-13. | **Yes.** CC BY-SA 4.0 has no NonCommercial element; s.2(a)(1) grants *"a worldwide, royalty-free, non-sublicensable, non-exclusive, irrevocable license"* to *"reproduce and Share the Licensed Material, in whole or in part"* and *"produce, reproduce, and Share Adapted Material"*. TVmaze's own gloss: "for any purpose". | Yes, a licence condition (s.3(a)). Satisfied per TVmaze's own instruction by linking to TVmaze URLs from within the app: `schedule.tvmaze_url` on every joined show and `url` on every episode. The attribution screen additionally names TVmaze, states "CC BY-SA 4.0", links the licence (s.3(a)(1)(c)) and says the data was reformatted (s.3(a)(1)(b)). | **Yes, on the snapshot file.** See below. The app code is not Adapted Material. |
| TheTVDB | nothing | Not read this session; not needed (TVmaze covers schedule). | **UNKNOWN — not used.** | — | — |

## LezWatch.TV, in full

**Grant.** The ToS ("The Gist") says, verbatim:

> By using this website, you agree to our terms of service. You are welcome to
> use, reuse, and extend the data here for no fees. We make no claims of
> copyright to the images found here, and believe them to fall under the
> fair-use clause. We do ask you link back to us, or note us by name, as a thank
> you in your final works.

and scopes itself to *"the database of queer females and related shows on the
LezWatch.TV News plugin and any API based services to display data on your own
site."* The API documentation adds *"There is currently no key required to use
this API, but there is a rate limit of a 100 requests per IP every 10 minutes."*

**What this is and is not.** It is a written permission in a terms-of-use page,
not a Creative Commons or ODC licence. It has no non-commercial clause, no
share-alike clause, and no termination clause; it can be changed by editing the
page. The pipeline therefore re-reads the ToS on every run and fails the build
if the "for no fees" sentence is gone (`pipeline/src/qtv_pipeline/terms.py`),
and the dated copy in `docs/terms-snapshots/` is the record of what was granted
when the app shipped.

**The scope question, and the request.** The same page scopes the terms to
"any API based services to display data on your own site". A paid iPhone app
is arguably not "your own site", so the owner decided (DECISIONS 0008) to ask
LezWatch.TV in writing before shipping. The draft, addressed to
`contact@lezwatchtv.com`, is in [moved to private strategy notes].
It also tells them that the combined snapshot, including their data, is
published under CC BY-SA 4.0. When they answer, save the reply beside the
draft and update the table row above.

**Not taken.** Images (the site's fair-use position is its own, not ours;
inline `<img>` tags inside LezWatch's prose fields are stripped with the rest
of the markup, so not even an image URL reaches the snapshot);
article/post content (editorial, not "the data"); anything about LezWatch's
users or contributors.

**Attribution the app shows.** On the attribution screen:

> Show and character data from LezWatch.TV (https://lezwatchtv.com), the
> volunteer-run database of queer female, non-binary and transgender characters
> on TV. Used with thanks under its terms of use; LezWatch.TV does not endorse
> this app.

and on every show and character screen, a link to `source_url`.

**Liability.** The ToS: *"this site shall not be responsible or liable for the
accuracy, usefulness or availability of any information."* The app's own
notice should say the same about itself.

**robots.txt** (https://lezwatchtv.com/robots.txt, read 2026-09-13):
`User-agent: *` … `Crawl-delay: 10`; `/wp-json/` is not disallowed. The
pipeline honours the 10-second delay even though it is stricter than the API's
published limit (100/10 min = one per 6 s).

## TVmaze, in full

**Grant.** CC BY-SA 4.0. The API page's own words are in the table. The licence
elements are Attribution and ShareAlike only.

**Attribution (s.3(a)).** If we Share the Licensed Material "(including in
modified form)" we must retain creator identification, a copyright notice, a
notice referring to the licence, a notice referring to the disclaimer of
warranties, and a link "to the extent reasonably practicable"; *"indicate if
You modified the Licensed Material"*; and *"indicate the Licensed Material is
licensed under this Public License, and include the text of, or the URI or
hyperlink to, this Public License."* s.3(a)(2): *"You may satisfy the
conditions in Section 3(a)(1) in any reasonable manner based on the medium,
means, and context."* TVmaze says a link back from within the application
satisfies it. The snapshot's `attribution[]` entry for TVmaze carries the text
below and the app shows it verbatim:

> Episode and schedule data from TVmaze (https://www.tvmaze.com), licensed
> under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).
> Reformatted for this app; TVmaze provides the data as-is without warranty and
> does not endorse this app.

**ShareAlike — does it attach to the bundled snapshot, and what does that oblige?**
Yes, it attaches to the snapshot file. s.4(b): *"if You include all or a
substantial portion of the database contents in a database in which You have
Sui Generis Database Rights, then the database in which You have Sui Generis
Database Rights (but not its individual contents) is Adapted Material, including
for purposes of Section 3(b)."* Whether ~2,300 shows' schedule rows out of
TVmaze's tens of thousands is "substantial" is arguable; we do not argue it. We
treat `snapshot.v1.json` as Adapted Material. Plainly:

- **The snapshot file is published under CC BY-SA 4.0.** The file says so in
  its `licence.snapshot` block (s.3(b)(2): include the URI of the Adapter's
  License), the GitHub Release and the Pages index say so, and the same bytes
  that ship inside the app are served at the public static URL so anyone can
  obtain the file under those terms (s.2(a)(5)(c) / s.3(b)(3): no
  "Effective Technological Measures" restricting the rights — the app bundle is
  not one, because the file is also openly published).
- **The app code is not.** The Swift app reads the file; it does not translate,
  alter or arrange TVmaze's data and is not "derived from or based upon" it
  (s.1(a)). It stays under whatever licence Chelsea chooses. Same for the
  pipeline code.
- **LezWatch's data inside the file** is not TVmaze's Licensed Material, but the
  file as a database is one work; publishing the whole file under BY-SA is
  consistent with LezWatch's "use, reuse, and extend … for no fees".
- **Obligation on anyone who redistributes the snapshot:** BY-SA 4.0 or a
  compatible licence, with attribution to TVmaze and LezWatch. That is what the
  `licence.notice` string says.

**Rate limit and etiquette** (https://www.tvmaze.com/api §Rate limiting, read
2026-09-13): *"API calls are rate limited to allow at least 20 calls every 10
seconds per IP address."* *"Leaving more than 1 connection to our servers idle
may result in your IP getting blocked."* *"we strongly recommend setting your
client's HTTP User Agent to something that'll uniquely describe it."* Output is
*"cached by our HTTP load balancers for 60 minutes"*. The pipeline runs one
connection, ≥1 s between calls, backs off on 429, and identifies itself.
`api.tvmaze.com` serves no robots.txt (HTTP 404, 2026-09-13);
`www.tvmaze.com/robots.txt` disallows `/stats`, `/offer` and user pages, none
of which the pipeline touches.

**Not taken.** Images (`image` fields point at files whose rights TVmaze does
not licence to us), episode summaries (prose, often third-party), cast, ratings.

## TheTVDB

Not needed: TVmaze supplies the schedule. Its terms were not read this session.
Status: **UNKNOWN, not used.** If it is ever needed, read
https://thetvdb.com/api-information first and fill the row.

## What the snapshot's `licence` and `attribution` blocks contain

`licence.notice` (shown verbatim on the attribution screen):

> This dataset is published under the Creative Commons Attribution-ShareAlike
> 4.0 International licence. Show and character data: LezWatch.TV. Episode and
> schedule data: TVmaze (CC BY-SA 4.0). If you redistribute this file, keep
> this notice and these credits.

`attribution[]`: the two source entries above, each with `url`, `licence_name`,
`licence_url`, `terms_url`, `terms_read_on`.

## Crawl budget and conduct (declared before the first mirror)

| | LezWatch.TV | TVmaze |
|---|---|---|
| Published limit | 100 requests / IP / 10 min | ≥20 calls / 10 s / IP |
| robots.txt | `Crawl-delay: 10` for `*` | none on `api.`; `www.` irrelevant |
| Pace used | **1 request / 10 s**, one connection | **1 request / s**, one connection, back off on 429 |
| Full mirror | ~23 show pages + ~74 character pages at 100/page (`_fields` trimmed), 12 taxonomy lists, 1 actor export, 2 id lists, 1 ToS read ≈ **115 requests ≈ 20 min, ~10 MB** | one `/shows/{id}?embed[]=nextepisode&embed[]=previousepisode` per joined show ≈ **2,000 requests ≈ 35 min, ~4 MB** |
| Nightly incremental | `modified_after=<cursor>` on shows and characters + the 2 id lists + taxonomies ≈ **20 requests** | shows with status Running/TBD/In Development or updated per `/updates/shows?since=day` ≈ **300 requests** |
| User-Agent | `queer-tv-guide-pipeline/<version> (+https://github.com/ChelseaKR/queer-tv-guide)` | same |
| Reported | request count and bytes per source, in the coverage report and in `sources.*` in the snapshot | same |

Requests made on 2026-09-13 before any mirror, for reading terms and sampling
field shapes: lezwatchtv.com 7, docs.lezwatchtv.com 3, api.tvmaze.com 3 (one
was a 301 followed once), www.tvmaze.com 2, creativecommons.org 1. Total 16.
