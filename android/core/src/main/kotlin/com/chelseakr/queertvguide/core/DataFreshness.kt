package com.chelseakr.queertvguide.core

import java.time.Duration
import java.time.Instant

/**
 * How old the snapshot on screen is, against the data cards' 48-hour SLA
 * (DG-04). Only [Current] is current; a snapshot dated after the device's
 * clock by more than [CLOCK_TOLERANCE_SECONDS] is [Unknown], and the UI
 * treats unknown exactly like stale.
 */
sealed class DataFreshness {
    data class Current(val ageSeconds: Long) : DataFreshness()
    data class Stale(val ageSeconds: Long) : DataFreshness()
    data object Unknown : DataFreshness()

    val isCurrent: Boolean get() = this is Current

    companion object {
        const val STALE_AFTER_SECONDS: Long = 48 * 60 * 60
        const val CLOCK_TOLERANCE_SECONDS: Long = 60 * 60

        /** Exactly [STALE_AFTER_SECONDS] old is still current; one second more is stale. */
        fun assess(generatedAt: Instant, now: Instant): DataFreshness {
            // Compared in milliseconds, as GuideCore compares fractional
            // seconds: 48 hours and half a second is already stale.
            val ageMillis = Duration.between(generatedAt, now).toMillis()
            if (ageMillis < -CLOCK_TOLERANCE_SECONDS * 1000) return Unknown
            val clamped = maxOf(0, ageMillis)
            return if (clamped > STALE_AFTER_SECONDS * 1000) Stale(clamped / 1000) else Current(clamped / 1000)
        }
    }
}

/**
 * When coming back to the app should look for new data: only once the
 * snapshot is more than [STALE_AFTER_SECONDS] old (or its age is unknown),
 * and at most once per [MINIMUM_INTERVAL_SECONDS] whatever triggered the last
 * look. In memory only: nothing about when someone opens the app is kept.
 */
class ForegroundRefreshGate(lastAttempt: Instant? = null) {
    var lastAttempt: Instant? = lastAttempt
        private set

    fun recordAttempt(now: Instant) {
        lastAttempt = now
    }

    /** Whether to look now; when yes, the attempt is recorded. */
    fun shouldRefresh(
        generatedAt: Instant,
        now: Instant,
        staleAfterSeconds: Long = STALE_AFTER_SECONDS,
        minimumIntervalSeconds: Long = MINIMUM_INTERVAL_SECONDS,
    ): Boolean {
        val ageMillis = Duration.between(generatedAt, now).toMillis()
        val ageUnknown = ageMillis < -DataFreshness.CLOCK_TOLERANCE_SECONDS * 1000
        if (!(ageUnknown || ageMillis > staleAfterSeconds * 1000)) return false
        lastAttempt?.let { last ->
            // A clock moved back past the last look cannot measure the interval: allowed.
            val sinceMillis = Duration.between(last, now).toMillis()
            if (sinceMillis >= 0 && sinceMillis < minimumIntervalSeconds * 1000) return false
        }
        lastAttempt = now
        return true
    }

    companion object {
        const val STALE_AFTER_SECONDS: Long = 3 * 24 * 60 * 60
        const val MINIMUM_INTERVAL_SECONDS: Long = 6 * 60 * 60
    }
}
