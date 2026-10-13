package com.chelseakr.queertvguide.widget

import androidx.core.net.toUri
import android.content.Context
import android.content.Intent
import android.text.format.DateFormat
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.LocalSize
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.SizeMode
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.appwidget.cornerRadius
import androidx.glance.appwidget.provideContent
import androidx.glance.appwidget.updateAll
import androidx.glance.background
import androidx.glance.color.ColorProvider
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.Spacer
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.height
import androidx.glance.layout.padding
import androidx.glance.semantics.contentDescription
import androidx.glance.semantics.semantics
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.MainActivity
import com.chelseakr.queertvguide.core.AppLink
import com.chelseakr.queertvguide.core.DateText
import com.chelseakr.queertvguide.core.UpNext
import com.chelseakr.queertvguide.core.UpNextPresentation
import com.chelseakr.queertvguide.core.UpNextStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/**
 * The Up Next home-screen widget: the next episode of each favorite show.
 * It reads one file the app writes ([UpNext]) and nothing else: no network
 * request, no snapshot, no death data. Every word comes from core's
 * [UpNextPresentation], which the parity file holds to GuideCore's. A row
 * opens its show; the rest of the widget opens the app.
 */
class UpNextWidget : GlanceAppWidget() {
    override val sizeMode: SizeMode = SizeMode.Responsive(setOf(SMALL, MEDIUM))

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val upNext = withContext(Dispatchers.IO) { UpNextStore(AppModel.upNextDirectory(context)).read() }
        val text = DateText(Locale.getDefault(), ZoneId.systemDefault()) { skeleton, locale -> DateFormat.getBestDateTimePattern(locale, skeleton) }
        provideContent { Content(context, upNext, Instant.now(), text) }
    }

    @Composable
    private fun Content(context: Context, upNext: UpNext?, now: Instant, text: DateText) {
        val small = LocalSize.current.width < MEDIUM.width
        val capacity = if (small) 1 else 3
        Column(
            modifier = GlanceModifier.fillMaxSize().background(Colors.background).cornerRadius(16.dp).padding(12.dp)
                .clickable(actionStartActivity(Intent(context, MainActivity::class.java))),
        ) {
            Text(UpNextPresentation.TITLE, style = TextStyle(color = Colors.accent, fontSize = 12.sp, fontWeight = FontWeight.Bold))
            Spacer(GlanceModifier.height(6.dp))
            if (upNext == null) {
                Message(UpNextPresentation.NOT_LOADED)
                return@Column
            }
            if (upNext.items.isEmpty() && upNext.missingShowCount == 0) {
                Message(UpNextPresentation.NO_FAVORITE_SHOWS)
            } else {
                val ordered = upNext.ordered(now)
                for (item in ordered.take(capacity)) {
                    ItemRow(context, item, now, text, small)
                    Spacer(GlanceModifier.height(4.dp))
                }
                UpNextPresentation.more(ordered.size - capacity, upNext.missingShowCount)?.let {
                    Text(it, style = TextStyle(color = Colors.subdued, fontSize = 11.sp))
                }
            }
            Spacer(GlanceModifier.defaultWeight())
            val stale = UpNextPresentation.freshness(upNext.snapshotGeneratedAt, now) != UpNextPresentation.Freshness.CURRENT
            val age = UpNextPresentation.dataAge(upNext.snapshotGeneratedAt, now, text)
            val credit = if (upNext.items.isEmpty()) null else UpNextPresentation.TVMAZE_CREDIT
            val footerStyle = TextStyle(color = Colors.subdued, fontSize = 11.sp, fontWeight = if (stale) FontWeight.Bold else FontWeight.Normal)
            if (small) {
                Text(age, style = footerStyle, maxLines = 1)
                credit?.let { Text(it, style = TextStyle(color = Colors.subdued, fontSize = 11.sp), maxLines = 1) }
            } else {
                Text(listOfNotNull(age, credit).joinToString(" · "), style = footerStyle, maxLines = 1)
            }
        }
    }

    @Composable
    private fun Message(text: String) {
        Text(text, style = TextStyle(color = Colors.subdued, fontSize = 13.sp))
    }

    @Composable
    private fun ItemRow(context: Context, item: UpNext.Item, now: Instant, text: DateText, small: Boolean) {
        val open = actionStartActivity(
            Intent(Intent.ACTION_VIEW, AppLink.ShowLink(item.showId).url.toUri(), context, MainActivity::class.java),
        )
        val line = UpNextPresentation.line(item, now, text)
        val spoken = UpNextPresentation.spoken(item, now, text)
        val titleStyle = TextStyle(color = Colors.primary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        val lineStyle = TextStyle(color = Colors.subdued, fontSize = 12.sp)
        if (small) {
            Column(GlanceModifier.fillMaxWidth().clickable(open).semantics { contentDescription = spoken }) {
                Text(item.title, style = titleStyle, maxLines = 2)
                Text(line, style = lineStyle, maxLines = 2)
            }
        } else {
            Row(
                GlanceModifier.fillMaxWidth().clickable(open).semantics { contentDescription = spoken },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(item.title, style = titleStyle, maxLines = 1, modifier = GlanceModifier.defaultWeight())
                Text(line, style = lineStyle, maxLines = 1)
            }
        }
    }

    /** The app's contrast-checked colors (ui/Theme.kt), day and night. */
    private object Colors {
        val background = ColorProvider(day = Color.White, night = Color(0xFF1E1E1E))
        val primary = ColorProvider(day = Color(0xFF111111), night = Color(0xFFF2F2F2))
        val accent = ColorProvider(day = Color(0xFF0057B3), night = Color(0xFF73B8FF))
        val subdued = ColorProvider(day = Color(0xFF404040), night = Color(0xFFC7C7C7))
    }

    companion object {
        val SMALL = DpSize(110.dp, 110.dp)
        val MEDIUM = DpSize(250.dp, 110.dp)

        suspend fun updateAll(context: Context) {
            UpNextWidget().updateAll(context)
        }
    }
}

class UpNextWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = UpNextWidget()
}
