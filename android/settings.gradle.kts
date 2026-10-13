// Queer Frame for Android (DECISIONS 0018). Two modules:
//   core -- plain Kotlin/JVM: the snapshot contract, every rule and every
//           sentence GuideCore has, tested on the JVM against GuideCore's own
//           fixture and parity file (ios/GuideCore/Tests/Fixtures/).
//   app  -- Jetpack Compose + Material 3 over core: screens, the one GET,
//           local reminders (WorkManager), the Up Next widget (Glance).
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "queer-frame-android"
include(":core", ":app")
