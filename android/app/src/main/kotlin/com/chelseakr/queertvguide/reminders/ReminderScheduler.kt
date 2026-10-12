package com.chelseakr.queertvguide.reminders

import androidx.core.net.toUri
import androidx.core.content.edit
import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.await
import com.chelseakr.queertvguide.MainActivity
import com.chelseakr.queertvguide.R
import com.chelseakr.queertvguide.core.AppLink
import com.chelseakr.queertvguide.core.DateText
import com.chelseakr.queertvguide.core.EpisodeReminders
import com.chelseakr.queertvguide.core.Snapshot
import java.time.Duration
import java.time.Instant

/**
 * Sets the optional episode reminders on this device: core's
 * [EpisodeReminders] plans them (the same plan as iOS), WorkManager holds
 * one delayed job per reminder, and each job posts a local notification.
 * No server, no push token, no account: nothing leaves the device.
 *
 * Does nothing at all unless the person turned reminders on.
 */
object ReminderScheduler {
    const val CHANNEL_ID = "episode-reminders"
    const val TAG = "episode-reminder"

    /** The person's choice, off until they turn it on (and, on Android 13+, allow notifications). */
    const val ENABLED_PREF = "reminders.v1.enabled"

    fun isEnabled(context: Context): Boolean = prefs(context).getBoolean(ENABLED_PREF, false)

    fun setEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit { putBoolean(ENABLED_PREF, enabled) }
    }

    private fun prefs(context: Context) = context.getSharedPreferences(com.chelseakr.queertvguide.AppModel.PREFS, Context.MODE_PRIVATE)

    fun createChannel(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        val channel = NotificationChannel(CHANNEL_ID, context.getString(R.string.reminder_channel_name), NotificationManager.IMPORTANCE_DEFAULT)
        channel.description = context.getString(R.string.reminder_channel_description)
        manager.createNotificationChannel(channel)
    }

    /** Whether a notification posted now could appear: permission granted and the app's notifications on. */
    fun canNotify(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    /**
     * Replaces this app's pending reminders with [plan]'s. Called after the
     * snapshot loads or refreshes and when the app leaves the foreground, so
     * starring or unstarring a show is reflected.
     */
    suspend fun reschedule(context: Context, snapshot: Snapshot, favoriteShowIds: List<String>, text: DateText, now: Instant = Instant.now()) {
        val work = WorkManager.getInstance(context)
        if (!isEnabled(context) || !canNotify(context)) {
            work.cancelAllWorkByTag(TAG).await()
            return
        }
        val plan = EpisodeReminders.plan(favoriteShowIds, snapshot, now, text)
        work.cancelAllWorkByTag(TAG).await()
        for (reminder in plan) {
            val request = OneTimeWorkRequestBuilder<ReminderWorker>()
                .setInitialDelay(Duration.between(now, reminder.fireAt))
                .setInputData(
                    Data.Builder()
                        .putString(KEY_ID, reminder.identifier)
                        .putString(KEY_SHOW, reminder.showId)
                        .putString(KEY_TITLE, reminder.title)
                        .putString(KEY_BODY, reminder.body)
                        .build(),
                )
                .addTag(TAG)
                .build()
            work.enqueueUniqueWork(reminder.identifier, ExistingWorkPolicy.REPLACE, request).await()
        }
    }

    suspend fun cancelAll(context: Context) {
        WorkManager.getInstance(context).cancelAllWorkByTag(TAG).await()
    }

    internal const val KEY_ID = "identifier"
    internal const val KEY_SHOW = "showId"
    internal const val KEY_TITLE = "title"
    internal const val KEY_BODY = "body"

    /** Posts one reminder. Its tap opens the show (`queerframe://show/<id>`): only the snapshot id, looked up locally. */
    fun post(context: Context, identifier: String, showId: String, title: String, body: String) {
        if (!canNotify(context)) return
        val intent = Intent(Intent.ACTION_VIEW, AppLink.ShowLink(showId).url.toUri(), context, MainActivity::class.java)
            .putExtra(AppLink.REMINDER_SHOW_ID_KEY, showId)
        val pending = PendingIntent.getActivity(
            context,
            identifier.hashCode(),
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(identifier, 0, notification)
        } catch (_: SecurityException) {
            // Permission withdrawn between the check and the post: nothing to show.
        }
    }
}

/** One reminder's delayed job: posts it, then is done. */
class ReminderWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(ReminderScheduler.KEY_ID) ?: return Result.failure()
        val show = inputData.getString(ReminderScheduler.KEY_SHOW) ?: return Result.failure()
        val title = inputData.getString(ReminderScheduler.KEY_TITLE) ?: return Result.failure()
        val body = inputData.getString(ReminderScheduler.KEY_BODY) ?: return Result.failure()
        if (ReminderScheduler.isEnabled(applicationContext)) {
            ReminderScheduler.post(applicationContext, id, show, title, body)
        }
        return Result.success()
    }
}
