package com.chelseakr.queertvguide.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/**
 * How dates are written: in the viewer's locale and time zone, as GuideCore's
 * `DateFormatter`s write them on iOS.
 *
 * - [mediumDay]: a UTC calendar day, medium style ("Sep 20, 2026"), for
 *   TVmaze's air dates, which are days in the network's time zone.
 * - [mediumDateTime]: an instant in the viewer's zone, medium date and short
 *   time joined by "at" as iOS joins them ("Sep 20, 2026 at 6:00 PM"). The
 *   app is US English only (docs/I18N.md), and this is the iOS wording.
 * - [skeleton]: a date from a skeleton such as "MMMd", the way iOS's
 *   `setLocalizedDateFormatFromTemplate` does; the app passes Android's
 *   `DateFormat.getBestDateTimePattern`, tests the JVM's.
 */
class DateText(
    val locale: Locale,
    val zone: ZoneId,
    private val bestPattern: (skeleton: String, locale: Locale) -> String = ::jvmBestPattern,
) {
    private val dateMedium = DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).withLocale(locale)
    private val timeShort = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT).withLocale(locale)
    private val patterns = HashMap<String, DateTimeFormatter>()

    fun mediumDay(day: LocalDate): String = dateMedium.format(day)

    fun mediumDateTime(instant: Instant): String {
        val local = instant.atZone(zone)
        return "${dateMedium.format(local)} at ${timeShort.format(local)}"
    }

    /** [instant] in this zone, written from [skeleton] ("MMMd" is "Sep 20" in US English). */
    fun skeleton(skeleton: String, instant: Instant): String = formatter(skeleton).format(instant.atZone(zone))

    /** A UTC calendar day written from [skeleton]. */
    fun skeletonUtcDay(skeleton: String, day: LocalDate): String = formatter(skeleton).format(day.atStartOfDay(ZoneOffset.UTC))

    private fun formatter(skeleton: String): DateTimeFormatter = synchronized(patterns) {
        patterns.getOrPut(skeleton) { DateTimeFormatter.ofPattern(bestPattern(skeleton, locale), locale) }
    }

    fun withZone(zone: ZoneId): DateText = DateText(locale, zone, bestPattern)

    companion object {
        /** US English in the device's zone, for code with no viewer to ask. */
        fun usEnglish(zone: ZoneId): DateText = DateText(Locale.US, zone)

        /**
         * US English patterns for the two skeletons the app uses, for the
         * JVM, which has no skeleton API on every version Android runs.
         * On a device the app passes `DateFormat.getBestDateTimePattern`
         * instead, and an instrumented test checks it gives the same words.
         */
        fun jvmBestPattern(skeleton: String, @Suppress("UNUSED_PARAMETER") locale: Locale): String = when (skeleton) {
            "MMMd" -> "MMM d"
            "MMMMd" -> "MMMM d"
            else -> skeleton
        }
    }
}
