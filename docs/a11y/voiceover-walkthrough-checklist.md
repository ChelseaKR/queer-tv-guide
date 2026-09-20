# VoiceOver walkthrough checklist

What to check by hand, on a real iPhone, before each release (A11Y-11,
A11Y-18; #22). Write the result up as
`docs/a11y/screen-reader-walkthrough-YYYY-MM-DD.md`.

**Status: not done yet.** Nobody has run this pass on a device. Until
someone does, make no claim that the app is VoiceOver-tested or meets WCAG.

## What the automated checks already cover, and what they miss

`make a11y` runs in CI (`ios/QueerTVGuideUITests/AccessibilityAuditTests.swift`,
iOS simulator). It covers:

- Xcode's accessibility audit on every screen: contrast, hit-target size,
  missing labels and traits, Dynamic Type support, clipped text.
- A check that a closed "does she die" answer is not in the accessibility
  tree, and that an unknown death reads "Not recorded", never "No".

It cannot tell you:

- whether the spoken order makes sense;
- whether a label is clear when heard, not just present;
- where focus lands after an action;
- how gestures, the rotor or a braille display behave;
- how things behave on a real device.

This checklist covers those gaps.

## Setup

- A real iPhone (not the simulator) on the current iOS release. Note the
  model and iOS version.
- VoiceOver on (Settings > Accessibility > VoiceOver). Set the Accessibility
  Shortcut to VoiceOver so a triple-click toggles it.
- Delete and reinstall the app first, so Favorites starts empty.
- Do the pass once with default settings. Then do it again with Larger Text
  at the maximum (Settings > Accessibility > Display & Text Size > Larger
  Text), Bold Text, Increase Contrast and Reduce Motion on. Do it once in
  Dark Mode.

## The primary tasks

Tick each row only if a VoiceOver user can do the task without sighted help.
Note anything confusing, even if the task was completed.

### 1. Search and browse with filters

- [ ] Each tab is announced by name, and the selected tab says so.
- [ ] The search field is announced, and typed text is echoed back.
- [ ] Results are reachable by swiping. A show row reads its title,
      worth-it verdict and network. A character row reads the name and the
      show.
- [ ] The Filter button opens the menu. Each filter reads as a toggle with
      its state. After you close the menu, it is clear a filter is on.
      Known issue (#22): the button reads "Filter (active)" instead of
      giving its state as a value.
- [ ] When a search finds nothing, "No matches" comes right after the search
      field when you swipe. Note whether you could tell the results changed
      without swiping.
- [ ] Pull to refresh works with a three-finger swipe down.

### 2. Open a show and reveal "Do any queer characters die?"

- [ ] Swipe through the whole show screen with the reveal closed. Nothing
      you hear says whether anyone dies. That includes tropes, trigger
      warnings, character rows, plot notes, links and hints.
- [ ] Headings (rotor > Headings) jump between the sections, including
      "Do any queer characters die?".
- [ ] The Reveal button reads its hint. Double-tapping it moves focus to
      the answer, and the answer is read in full.
- [ ] If no death is recorded, the answer starts with "Not recorded". It
      never starts with "No" and never says anyone survives.
- [ ] "Plot notes (may contain spoilers)" stays closed until you open it.

### 3. Open a character and reveal "Does she die?"

- [ ] The same checks as task 2, on the character screen. The heading
      names the character.
- [ ] A recorded death reads "Yes. <name> dies …". An unknown one reads
      "Not recorded. …".
- [ ] Going back and returning to the screen closes the reveal again.

### 4. Add and remove a favorite

- [ ] The star button reads "Add to favorites". After a double-tap, it
      reads "Remove from favorites". Known issue (#22): the state is in the
      label, not a value or trait.
- [ ] The Favorites tab lists the item, and its row reads the next episode.
- [ ] Removing the item works through the Actions rotor (swipe up or down
      to "Delete"), and through Edit.
- [ ] Once the list is empty, "No favorites yet" and its message are read.
- [ ] The … menu button reads "Back up or restore favorites". Its menu
      reads "Export favorites" (dimmed, and said to be, while the list is
      empty) and "Import favorites".
- [ ] Export opens the share sheet; saving to Files works with VoiceOver.
      Import opens the file picker; after picking a backup, the alert that
      says how many favorites were added is read out, and focus returns to
      the list.

### 5. Out-of-date data

Set the device's date two weeks ahead (Settings > General > Date & Time,
automatic off), open the app offline, and set it back afterwards.

- [ ] At the top of Search, one element reads "Warning. This data is out of
      date. It was last updated … days ago …" in full.
- [ ] The same warning is at the top of a non-empty Favorites list.
- [ ] The data line at the bottom of each screen reads "This data is out of
      date." before "Data as of …".

### 6. Open a where-to-watch link

- [ ] Each link reads its host and the hint "Opens … in Safari".
- [ ] A double-tap opens Safari. Returning to the app puts you back where
      you were.

### 7. About, attribution and privacy

- [ ] Section headings are announced as headings.
- [ ] The privacy text, data sources, license and coverage figures are all
      reachable and make sense read aloud ("LezWatch.TV" reads as a name,
      not "dot T V").
- [ ] The Privacy policy, Support and source links read as links or buttons,
      with a hint that they open Safari.

## At the largest text size

- [ ] On every screen above, no text is cut off, overlapped or truncated
      with "…", except where a row lets you open it in full.
- [ ] Rows stack instead of squeezing, and everything can be reached by
      scrolling.
- [ ] The tab bar and toolbar buttons can still be used.

## Recording the result

In `docs/a11y/screen-reader-walkthrough-YYYY-MM-DD.md`, record:

- the date and who did the pass;
- the device model, iOS version and app build;
- the settings used;
- each row above, marked pass, fail or n/a, with a note for anything that is
  not a clean pass;
- a link to the issue filed for each failure.

A pass on one release does not carry over to the next. Run it again when a
screen changes.
