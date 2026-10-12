package com.chelseakr.queertvguide.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.io.File

/** Files in the repository the tests read in place (Gradle passes the root). */
object Repo {
    val root: File = File(
        System.getProperty("qf.repoRoot") ?: error("qf.repoRoot is not set; run the tests through Gradle"),
    )

    /** GuideCore's hand-made 4-show, 5-character fixture: the same input both platforms test against. */
    val fixtureFile: File = File(root, "ios/GuideCore/Tests/Fixtures/snapshot.fixture.json")

    /** What GuideCore says for the fixture (ParityGoldenTests.swift writes it). */
    val goldenFile: File = File(root, "ios/GuideCore/Tests/Fixtures/parity.golden.json")

    /** The snapshot the Android app ships: the published file, fetched by `make -C android bundle-snapshot`. */
    val bundledSnapshot: File = File(root, "android/app/src/main/assets/snapshot.v1.json")

    val androidRoot: File = File(root, "android")

    fun fixtureBytes(): ByteArray = fixtureFile.readBytes()

    fun fixture(): Snapshot = SnapshotDecoder.decode(fixtureBytes())

    fun fixtureJson(): JsonObject = Json.parseToJsonElement(fixtureFile.readText()) as JsonObject

    fun bytes(json: JsonElement): ByteArray = json.toString().toByteArray(Charsets.UTF_8)
}

/** Edits a JSON tree, so a test can make a near-real document with one field changed. */
object JsonEdit {
    fun JsonObject.with(key: String, value: JsonElement): JsonObject = JsonObject(toMutableMap().also { it[key] = value })

    fun JsonObject.without(key: String): JsonObject = JsonObject(toMutableMap().also { it.remove(key) })

    fun JsonObject.editArray(key: String, index: Int, edit: (JsonObject) -> JsonObject): JsonObject {
        val array = (this[key] as JsonArray).toMutableList()
        array[index] = edit(array[index] as JsonObject)
        return with(key, JsonArray(array))
    }

    fun JsonObject.editObject(key: String, edit: (JsonObject) -> JsonObject): JsonObject = with(key, edit(this[key] as JsonObject))

    fun str(value: String?): JsonElement = if (value == null) JsonNull else JsonPrimitive(value)
}
