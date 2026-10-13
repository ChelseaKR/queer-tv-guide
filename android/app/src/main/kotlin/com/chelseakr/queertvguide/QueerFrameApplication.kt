package com.chelseakr.queertvguide

import android.app.Application
import android.content.Context
import com.chelseakr.queertvguide.reminders.ReminderScheduler

/** Holds the one [AppModel]; creates the reminder channel. No SDK is initialized here, because there are none. */
class QueerFrameApplication : Application() {
    val model: AppModel by lazy { AppModel.create(this) }

    override fun onCreate() {
        super.onCreate()
        ReminderScheduler.createChannel(this)
    }
}

val Context.appModel: AppModel get() = (applicationContext as QueerFrameApplication).model
