plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}

// Java 17 bytecode, so the Android app (and D8) take it as it is; built by
// whichever JDK runs Gradle (21 locally and in CI).
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        allWarningsAsErrors.set(true)
    }
}

dependencies {
    implementation(libs.kotlinx.serialization.json)
    testImplementation(libs.junit)
}

tasks.test {
    // The repository root, so tests read GuideCore's fixture and parity file
    // (ios/GuideCore/Tests/Fixtures/) and the bundled snapshot in place.
    systemProperty("qf.repoRoot", rootProject.projectDir.parentFile.absolutePath)
    // The JVM's default zone and locale must not decide any assertion:
    // every test passes its own. Pinned to ones the app never assumes, so a
    // test that leans on the default fails here rather than passing by luck.
    systemProperty("user.timezone", "Pacific/Chatham")
    systemProperty("user.language", "fr")
    systemProperty("user.country", "CA")
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
