package com.chelseakr.queertvguide.core

import java.net.URLEncoder

/**
 * The About screen's "Email support" row (DECISIONS 0039), the twin of
 * GuideCore's `SupportEmail`: a `mailto:` link to the address the support page
 * and the Play listing give, handed to the person's own mail app. The app
 * sends nothing itself, and nothing about the device or what someone follows
 * goes in the draft. The subject names the app and its version.
 */
object SupportEmail {
    const val ADDRESS = "chelsea@chelseakr.com"

    /** "<app name> <version>", or the app name alone when the version is missing or blank. */
    fun subject(appName: String, version: String?): String {
        val v = version?.trim().orEmpty()
        return if (v.isEmpty()) appName else "$appName $v"
    }

    /** `mailto:<address>?subject=<subject>`; every reserved character in the subject is percent-encoded. */
    fun uri(appName: String, version: String?): String {
        val encoded = URLEncoder.encode(subject(appName, version), "UTF-8").replace("+", "%20")
        return "mailto:$ADDRESS?subject=$encoded"
    }
}
