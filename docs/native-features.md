# Native feature matrix (VGA + AdLib)

The original-content feature matrix of the native build for the primary
configuration (DOS VGA, AdLib), in the form required by
[semantic-audit.md](semantic-audit.md) (native runtime completeness). Other
original paths are listed at the end and are not discarded.

Statuses: VERIFIED (bounded original/native differential cases exercise the
feature's routines and their composed handoff), PARTIALLY_VERIFIED (part of
the feature path, or only isolated routines, are compared), IMPLEMENTED_UNTESTED
(native code or host service exists, no differential case), INTENTIONALLY_UNSUPPORTED,
BLOCKED (the native build stops before or inside the feature), UNRESOLVED.

"Host" means the headless native runner (`host/main.c`, `host/platform_host.c`,
`host/README.md`). "Host-observed" means a short hand-written input script run on
`build/lemmings-headless.exe` reached the feature; scripts, logs and frame
captures are in `build/scratch/features/`. Host observation is integration
evidence, not a differential comparison. That executable stops at its fixed
100,000-poll budget, after about 141 gameplay frames (about 10 s of play); this is
a known host limit, not a feature gap.
Suite names are `tools/difftest.py` suites (`tests/<name>.py`); routine addresses
are main-image offsets from `metadata/symbols.json`.

## Startup

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Program entry, PSP, arena, MAIN.DAT sections, handoff to the menu | ProgramEntry 0000, AllocateStartupGraphicsArena 1007, LoadMainResourceSections 58D2, sprite/mask generators 59BB..5D66 | c/startup.c, c/main_resources.c and generators; `lmn_host_boot` (native PKLITE load, 63 relocations) | startup, main_resources, host_vga (native boot, arena, MAIN.DAT output hashes), host_journey (native startup-to-menu every poll to 446D) | VERIFIED |
| Command-line switches /a /e /v /n /d /p /o /x /m /2 /4 /i | ParsePspCommandLine 1293, ParsePspTimerReloadDecimal 13A8 | c/startup.c | startup: 12 command tails including all switches, case folding, /i edge values | VERIFIED (host passes only `/v /o` or `/v /o /a`) |
| Machine-type screen (VGA/EGA, PC, high-performance, PS/2, Amstrad, exit) | SelectStartupDisplayAndOptions 106E, MarkStartupOptionAndRedraw 1194 | c/startup.c | startup: option keys, arrows, exit row, escape | PARTIALLY_VERIFIED: host requires /o (DOS AH07 is unbound and fails) |
| Video adapter probe, raster/PIT timer calibration | DetectVideoAdapters 13DC..1523, CalibrateGameTimerReload 15AD, MeasureRasterPitCounter 1602 | c/video_probe.c; host declared colour-VGA machine (BIOS 1A00/12 answers, CRTC-derived raster) | video_probe, startup, host_vga (VGA known answers, detection 03/03, 355-line reload) | VERIFIED |
| Sound driver selection (AdLib detect, Tandy probe, PC-speaker fallback), adlib.dat load, INT61 install | InitializeSoundDriver 054E, ProbeTandyVideoPage 060C | c/sound_driver_init.c; host binds the installed INT61 to c/adlib_engine.c | sound_driver_init; host smoke with `--sound=adlib` | VERIFIED |
| Protection counter (russell.dat) and skip decision | CheckStartupProtection 062B, WriteProtectionCounterFile 0EC2 | c/protection.c; host read-only DOS files | protection (PASS, reject, skip, file errors); host_vga forced policy profiles | PARTIALLY_VERIFIED: host denies the create/write, so the counter never advances on disk (shipped byte 08 becomes 09 and skips the probe every run) |
| Original-floppy media probe and INT1/INT3 protected streams | ProbeOriginalFloppyMedia 063E, 0659, ProtectionInt3Handler 0DB3, 0DBD (UNTRANSLATED) | host `media_probe` named policy (`--media-probe=assume-original/reject/unsupported`) | protection (raw probe parity on original-built fixtures); host_vga policies | PARTIALLY_VERIFIED: platform substitution; probe body not translated, PASS result is an explicit policy |
| Keyboard, timer, INT24, mouse hooks and private vector install | InstallKeyboardVector 1562, InstallGameTimerVector 1644, InitializeMouseDriverHooks 0F08, startup 006A..008D | c/keyboard_input.c, c/timer_tail.c, c/startup.c; host IVT/INT33 | startup, timer_install, keyboard_input | VERIFIED |

## Front end

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Main menu screen (mode 10, backdrop, scroller, animations, palettes) | EnterMainMenu 43F2, MenuRefresh 4401, menu_* routines 4E37..4FF8, 7CBC..7E76 | c/main_menu.c, menu_animation.c, menu_scroll.c, menu_cache.c | main_menu, menu_animation, menu_scroll, menu_cache, menu_timer, game_loop, host_journey; host-observed (menu capture) | VERIFIED |
| F1 / mouse button: play | keyboard 80 or button bits 0..2 -> MainMenuStartLevel 454C | c/main_menu.c, c/level_start.c via `lmn_game_loop_core` | main_menu, game_loop, host_journey; host-observed | VERIFIED |
| F2: level code entry, valid and invalid codes, BILLANDTED latch | 4967 screen, ReadCodeInput 4C7E, EncodeLevelCode 5042, DecodeLevelCode 51A2, FormatSelectedLevelAndGroup 488C | c/main_menu.c (`lmn_show_code_entry_polled`) | main_menu: all 256 selections, failure stages; game_loop/host_journey type BILLANDTED; host-observed: valid codes for all 120 selections accepted | VERIFIED |
| F3: sound option cycle (music+effects, off, effects only) | sound branch at keyboard 82, table CS:44E9, SoundOptionBits 25A7 | c/main_menu.c | main_menu (exact index wrap, driver gate); host-observed with AdLib: one press gives no INT61 traffic, two presses keep effects and drop music | VERIFIED |
| Rating selection Fun/Tricky/Taxing/Mayhem (arrows, ` and -) | keyboard 8A/60, 8B/2D; group 1F6E, selection 1F6B | c/main_menu.c | main_menu (guards, byte wrap); host-observed (two increases give Taxing 1) | VERIFIED |
| F4: input selection (mouse, joystick calibration, keyboard) | ShowInputSelection 4A01..4AC4, ChooseInputController 43CE | c/keyboard_input.c (`lmn_show_input_selection_polled`) | keyboard_input, main_menu handoff; host-observed: mouse and keyboard choices return to the menu | PARTIALLY_VERIFIED: joystick choice stops the host at port 201 |
| Esc: exit to DOS | keyboard 1B -> DatFatalTransfer 04D0 cleanup | c/fatal_cleanup.c (restore timer, vectors, video, DOS 4C) | fatal_cleanup, file_error; host-observed: loop returns `LMN_GAME_LOOP_FATAL_CLEANUP` at 04D0 | PARTIALLY_VERIFIED: the runner stops at 04D0 and does not run the cleanup core |

## Level load and briefing

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Level resource selection for all 120 selections (LEVEL, GROUND, VGAGR, DAT cache) | LoadSelectedLevelResources 197D, order bytes DS:54EE, DAT routines 1B79..1ED7 | c/resource_select*.c, dat*.c, cache_allocation.c | resource_select (one real level per graphics/special kind plus a real odd override), resource_select_full, dat suites; host-observed: all 120 selections reach gameplay frame 3 | VERIFIED |
| Odd-table levels (40 selections) | odd override at 197D, oddtable.dat into DS:5566 | c/resource_select.c | resource_select real odd case; host-observed (Tricky 3 and all odd selections load) | VERIFIED |
| Special-graphics levels (Fun 22, Tricky 14, Taxing 15, Mayhem 22; vgaspec0..3) | SetupSpecialGraphicsResource 1A7B, special strips 8238..824F, reached from RedrawLevel 394F | c/special_setup.c, special_blit.c; level initialize and the host briefing redraw bind them | special_setup, special_blit, level_initialize (real special payloads), level_briefing special stop; host_smoke Fun 22 case; all 120 selections reach gameplay in the host | VERIFIED |
| Briefing screen, preview, texts, fades, wait for button | ShowLevelBriefing 4566, DrawLevelPreview 7EB2, palette 46A2/46B9/5329/534B | c/level_briefing.c, level_preview.c, palette_transition.c | level_briefing, level_preview, palette_transition, level_start, game_loop; host-observed | VERIFIED |
| Level initialization (header, terrain, objects, steel, status bar, drawing pages) | InitializeLevelFromRecord 36B6, RedrawLevel 394F, InitializeStatusDisplay 39CE, InitializeGameDrawingPages 81CC | c/level_initialize.c, level_redraw.c, terrain_*.c, object_*.c, steel_cells.c, game_prepare.c | level_initialize, level_redraw, terrain_stream, object_* suites, game_initialize, game_session | VERIFIED |
| Insert-disk / resource retry screen | ShowResourceRetryScreen 4B1C, CheckMenuResourceAvailability 4AC5 | c/resource_retry.c, retry_ui.c; game_loop retry connector | resource_retry, retry_input, game_loop; host-observed: selection 160 stays in the retry loop (4B40) | VERIFIED |

## Gameplay

Skill labels follow the panel order; the ledger names only action selectors
2..9 and their counts at DS:006A..007F (from LEVEL header +08..+16).

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Frame loop, session start, opening/closing fades | InitializeGameSession 03E7, session 00FB, AdvanceGameTransitionEffects 031E | c/game_session.c, game_frame.c, game_transition.c | game_session (gameplay and time-up scenarios), game_frame, game_transition, game_loop | VERIFIED |
| Release of lemmings, creation, population limit | CreateEntityRecordIfDue 30A6 | c/entity_create.c | entity_create, game_session (release cue creates a creature) | VERIFIED |
| Walking, falling, terrain sampling, turning | AdvanceEntityRecords 1F19, zero-state 2047, state handlers 2350.. | c/entity_update.c, entity_zero_state.c, entity_state*.c | entity_update (every state dispatch composed), entity_zero_state, state suites, game_session (land and walk) | VERIFIED |
| Climber (selector 2, +24 bit 0) | 329B; climbing state handlers | c/entity_actions_basic.c, entity_state*.c | entity_actions_basic, entity_select_actions, state suites, game_session (panel ordinal 2 assignment consumes one item) | VERIFIED |
| Floater (selector 3, +25 = FF) | 3557; falling states | c/entity_actions_basic.c | entity_actions_basic, state suites | VERIFIED (per-frame; no composed multi-frame case) |
| Bomber (selector 4, +20 = 4F countdown), explosion | 31C4, AdvanceEntityCountdown 2E04, countdown-expiry states | c/entity_actions_basic.c, entity_countdown.c, entity_state*.c | entity_actions_basic, entity_countdown, entity_update; host-observed countdown digits | VERIFIED (per-frame; explosion not reached in host runs) |
| Blocker (selector 5, interaction-map rows 02/0A/03) | 3336..34CD, CopyEntityPatternToInteractionMap 283B | c/entity_action_map.c, entity_pattern.c | entity_action_map (producer/restorer handoffs); host-observed: blocker stands, others turn, panel count drops | VERIFIED |
| Builder (selector 6, state 0080) | 32BD..3335, state 0080 | c/entity_actions_advanced.c, entity_state80.c | entity_actions_advanced, entity_state80 | VERIFIED (per-frame; not host-observed) |
| Basher (selector 7, state 0200, one-way/steel exclusions) | 34CE..3556, state 0200 | c/entity_actions_advanced.c, entity_state200.c | entity_actions_advanced, entity_state200 | VERIFIED (per-frame; not host-observed) |
| Miner (selector 8, state 0800) | 3598..3633, state 0800 | c/entity_actions_advanced.c, entity_state800.c | entity_actions_advanced, entity_state800 | VERIFIED (per-frame; not host-observed) |
| Digger (selector 9, state 0010) | 320D..3286, state 0010 | c/entity_actions_advanced.c, entity_state10.c | entity_actions_advanced, entity_state10; host-observed (count 10 -> 09, digging) | VERIFIED |
| Skill select: F3..F10, panel ordinals 2..9 | ProcessInputCommands 3E6F | c/ui_commands.c | ui_commands, game_session; host-observed (F10, panel blocker) | VERIFIED |
| Release rate: F1/F2, panel ordinals 0/1 | 3E6F -> 4068/403D/4032 | c/ui_commands.c | ui_commands; host-observed (held F2: 50 -> 54) | VERIFIED |
| Pause: F11, keypad +, panel ordinal 0A | 3E6F -> 4018 (gate 002B) | c/ui_commands.c | ui_commands, game_session (toggle/hold/resume); host-observed panel pause | VERIFIED |
| Nuke: F12, Delete, panel ordinal 0B (second press within five counter steps) | 3E6F -> 3FEF, scan request 004B | c/ui_commands.c, entity_update.c | ui_commands, entity_update scan path; host-observed: double F12 puts countdowns on all lemmings | VERIFIED |
| Quit level (Esc) to results | game-end request, session exit to 46EB | c/game_frame.c | game_session (quit scan reaches closing request); host-observed: Esc reaches the result screen | VERIFIED |
| Cheat level skip (BILLANDTED latch with scan 4C) | latch 1F74, key mask bit 8000 | c/game_frame.c | game_loop and host_journey (cheat/next journey) | VERIFIED |
| Scrolling (mouse edge, selector keys) | HandleSelectorKeysAndEdgeScroll 4085, RebuildViewVisibilityMap 410F | c/view_scroll.c, view_visibility.c | view_scroll, view_visibility, game_session (edge scroll right and back); host-observed | VERIFIED |
| Minimap and minimap click | UpdateMinimapColumn 796F, DrawMinimapViewport 7A5A, 3E6F -> 3F92 | c/minimap_*.c, ui_commands.c | minimap suites, ui_commands; host-observed (click jumps the view) | VERIFIED |
| Cursor, candidate selection, hover text | SelectEntityCandidate 3CDE, cursor sprites, status text 417B | c/entity_select.c, status_text.c | entity_select, entity_select_actions, game_session; host-observed (box cursor, "BLOCKER 1") | VERIFIED |
| Status bar (OUT, IN %, TIME, skill counts, icons) | UpdateStatusDisplay 3AC8, DrawStatusCount 762A, status icons 780D/789E | c/status_*.c | status suites; host-observed | VERIFIED |
| Objects and animation (trapdoor, exits, traps) | AdvanceLevelObjectAnimations 3944, DrawLevelObjectGraphics 7BB8, object cells 37C2 | c/object_*.c | object_animation, object_drawing_tick, object_cells(_bus), object_drawing; host-observed trapdoor | VERIFIED |
| Interaction cells: exit (kind 1), trap (4), hazards (5, 6), blocker/turn (2, 3), one-way (7, 8), steel (9) | ApplyEntityCellInteractions 2EC0, WriteSteelInteractionCells 3839, basher/miner nibble tests | c/entity_interactions.c, steel_cells.c, entity_actions_advanced.c | entity_interactions, steel_cells(_bus), entity_actions_advanced | VERIFIED (per-frame; no saved lemming or trap kill seen in host runs) |
| Time limit and time-up | countdown in frame loop | c/game_frame.c | game_session time-up, game_loop/host_journey (zero-minute level) | VERIFIED |
| Lemming record spill beyond 80 (selections 156/158/212/214 after an odd load) | CreateEntityRecordIfDue 30A6, characterized escape at 715B | C over canonical memory, explicit unknown-callback stop | entity_create; six planned cases pending (next-work.md) | PARTIALLY_VERIFIED |

## Results, progression and end

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Result screen, percentages, assessment text | LevelResultScreen 46EB, DrawResultPercentagesAndPrompt 48BD, DrawResultAssessmentMessage 48F6 | c/level_result.c | level_result: pass/fail per input mode, every message boundary, time-up, all-out | VERIFIED |
| Next level after success, crossing a rating boundary | 46EB -> 4551 with next selection | c/level_result.c, game_loop.c | level_result (group boundary 29, wrap 255), game_loop/host_journey (cheat/next) | VERIFIED |
| Retry after failure | 46EB -> 4551 same selection | c/level_result.c | level_result, host_journey (time-up/retry); host-observed (Esc -> result -> click -> level restarts) | VERIFIED |
| Return to menu from results | 46EB -> 4401 | c/level_result.c | level_result, game_loop/host_journey (menu return) | VERIFIED |
| Game end after the last level (selection 77h) | final result path 4812 | c/level_result.c | level_result final cases | PARTIALLY_VERIFIED: isolated screen only, never reached by a composed run |

## Rendering

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Mode 10 menus/briefing, mode 0D gameplay, page swap, CRTC start | SetupDisplayModeAndLayout 4BE7, SwapDrawingOriginsAndDisplay 4C20, ProgramDisplayStartFromValue 4C36 | c/display_*.c; host VGA (4 planes, latches, write modes 0..3, read modes 0/1) | display suites, host_vga (generated device traces), host smoke PPMs | VERIFIED |
| Terrain, sprites, masks, generated banks, text | DrawPlanarBitmap 8822, sprite routines 6170..7218, DrawTextStream 4D4D | c/drawing_*.c, entity_sprite_*.c, text_*.c | drawing, sprite, mask and text suites | VERIFIED |
| Palettes, fades, DAC/attribute writes | palette routines 52F4..570C, game fades 03C1/03D7 | c/palette_*.c, game_transition.c | palette suites, palette_timer, game_transition | VERIFIED |
| Raster split palette (playfield/panel) | RefreshRasterSplitPalette 46B9, timer palette 5473/553D | c/palette_transition.c, palette_ports.c; host beam-raced scanout | palette_transition, palette_timer; host: panel colours written at scanline 320, playfield restore at 412 | VERIFIED (split line measured; IRQ delivery at polls can add up to ~3 lines) |
| Live display | VGA scanout | host/sdl_main.c: each frame the emulated beam completes, 4:3 letterbox | host_smoke --sdl (offscreen, 130 frames identical to the headless runner, audio delivery within one frame of game time) | VERIFIED for scripted runs; live input feel unconfirmed |

## Audio

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| AdLib music, one song per level | SelectLevelSoundId 482F, AdLib update 0115 from timer 1872 | c/game_prepare.c, c/adlib_engine.c; host Nuked OPL3 (OPL2 mode) with per-access bus timing | game_prepare, adlib_engine (shipped songs per INT61 call), sound_latches; host smoke: music RMS and note onsets in audio.wav | VERIFIED (OPL core differences are unverified equivalence) |
| AdLib effects (entity, panel, interaction requests AH 04) | RequestEntityActionFeedback 31E5, 3F7A, 2F9F/2FF5/304C/30A3 | c/entity_action_sound.c, ui_commands.c, adlib_engine.c | entity_action_sound, entity_interactions, adlib_engine; host-observed effects with music off | VERIFIED |
| Live audio output | OPL ports 0388/0389 | host/sdl_main.c: OPL output streamed to an SDL audio stream (WAV with `--audio` in the headless runner) | host smoke (WAV level and onsets); SDL stream not compared automatically | IMPLEMENTED_UNTESTED for the device; samples identical to the WAV path |
| PC-speaker effects (default `/a` profile) | INT60 component 0842:0182, MAIN.DAT section 5 | c/pcspeaker*.c (4 entries TESTED); host INT60 is a muted, counting sink | pcspeaker, pcspeaker_bus, pcspeaker_dispatch, pcspeaker_interrupt | PARTIALLY_VERIFIED: no audio rendered |

## Input and timing

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Mouse (INT33 position/buttons, ranges) | PollMousePosition 4252, InitializeMouseDriverHooks 0F08 | c/input_poll.c; host INT33 0/2/3/4/7/8/0F/0C | input_poll, startup (mouse absent), host_journey | VERIFIED (scripted events only) |
| Keyboard IRQ, bindings, character table, keyboard control mode | KeyboardIrqHandler 16D4, ReadKeyboardCharacter 4D1A, PollInputState 418C | c/keyboard_input.c, input_poll.c; host IRQ09 at polls | keyboard_input, input_poll, game_session; host-observed keyboard mode reaches gameplay | VERIFIED |
| Mouse callback and private mouse IRQ bridge | MouseEventReturn 0F6F (RETF, UNTRANSLATED), MouseIrqBridge 0F70 | c/mouse_irq_bridge.c; host accepts only the 0F6F registration and never raises the private IRQ | mouse_irq_bridge | IMPLEMENTED_UNTESTED in host: platform substitution (host mouse never touches VGA registers) |
| Game and menu timers, BIOS chain, display-locked tick | GameTimerIrqHandler 17C7, MenuTimerIrqHandler 4C47, GameTimerTail 183E, 1872 | c/timer_tail.c; host PIT counting the programmed reload, CRTC-derived 70.09 Hz raster, IRQ08 delivered at polls | timer_tail, game_timer, menu_timer, palette_timer, host smoke (5 IRQ08 per game frame, 5 VGA frames within one poll quantum), host_vga | PARTIALLY_VERIFIED: IRQs arrive only at foreground polls, never inside a child or ISR |

## Files, errors and persistence

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| DAT/raw file reads, cache, decoder | 1916, 1B79..1ED7 | c/dat*.c, resource_raw*.c; host read-only DOS 3D/3F/3E/43/23 | dat suites, resource_raw(_full), host_journey | VERIFIED |
| DOS file error screen, fatal cleanup | 1949 file error, 04D0 cleanup | c/file_error.c, fatal_cleanup.c | file_error, fatal_cleanup | VERIFIED as routines; host stops at the cleanup handoff |
| INT24 critical error | CriticalErrorHandler 18F8 | c/dat_files.c | dat_files | IMPLEMENTED_UNTESTED in host (no critical errors raised) |
| Persistence (russell.dat counter; the only file the game writes) | WriteProtectionCounterFile 0EC2 | c/protection.c; host returns access denied | protection | PARTIALLY_VERIFIED: nothing persists between runs |

## Alternatives in this executable

| Feature | Original evidence | Native implementation | Verification | Status |
|---|---|---|---|---|
| Tandy sound driver (tandysnd.dat) | ProbeTandyVideoPage 060C, Tandy dispatch 02BB (39 of 43 entries untranslated) | dispatcher prefix and latch setters only; host stops on a non-AdLib INT61 image | sound_latches | UNRESOLVED |
| PC-speaker audio rendering | INT60 component | C engine present, host muted | pcspeaker suites | IMPLEMENTED_UNTESTED in host |
| Joystick (port 201) and calibration | PollPort201ButtonsLow 4334, PollPort201ButtonsHigh 4359, MeasurePort201Axes 4386, 4A4E.. | c/port_io.c, keyboard_input.c | port_io, keyboard_input | BLOCKED in host: port 201 unbound ("unbound input port") |
| EGA game (/e, attribute palette) and machine types (/x, /p, /d, /m, /2, /4) | 106E menu, WriteAttributePalette 5425, /x MAIN.DAT section 6 at 597D | C cores in startup, palette_ports, timer and input units | startup, palette_ports | IMPLEMENTED_UNTESTED in host (runner fixes the command line) |
| CGA/Tandy graphics files (cga*.dat, tgamain.dat) | not referenced by this executable (its file table names only VGA files, adlib.dat, tandysnd.dat, russell.dat) | - | - | not applicable |

## Blocking gaps for a playable VGA + AdLib build

In impact order:

1. **Live device polish.** The SDL3 front end (host/sdl_main.c) presents the
   scanout, streams OPL audio, maps keys to set-1 IRQ09 bytes and the mouse to
   the INT33 range, and paces PIT time by the wall clock; scripted runs match
   the headless runner frame for frame. Remaining: PC-speaker audio, joystick,
   and a human check of input feel and pacing.
2. **IRQ delivery granularity.** The host is now one declared machine (colour
   VGA, CRTC-derived raster, PIT counting its reload; host/README.md), and the
   game's own calibration places the panel split at scanline 320. IRQs are
   still delivered only at foreground polls (up to ~3 lines late, never inside
   a child or ISR); state which original interleavings that omits (the
   creation race stays characterized original behavior).
3. **Exit to DOS not composed.** Original dependency: 04D0 cleanup (timer,
   vectors, video mode, DOS 4C). The loop stops at 04D0. Needed: run
   `lmn_fatal_cleanup_core` and map its terminal DOS request to application exit.
4. **Protection persistence and media policy.** Original dependency:
   russell.dat counter writer 0EC2 and the untranslated probe 063E/INT1/INT3
   streams. Needed: a release decision: persist the counter in a writable
   location (the probe then runs periodically and needs the named policy) or
   keep the read-only skip, stated as a platform substitution.
5. **Composed coverage of long play.** Multi-frame skill lifecycles, saved
   lemmings at exits, trap kills, explosions and the game end after selection 77h
   are verified only per routine or per screen. Needed: longer bounded host
   journeys once the poll budget is lifted, then human-recorded replays.

Not blocking VGA + AdLib: PC-speaker audio (muted sink), Tandy engine
(untranslated), joystick (port 201 unbound), the machine-type screen without
/o, EGA and machine-type options, and the private mouse IRQ 0F70 (never
delivered; the host mouse driver does not touch VGA registers).

Resolved since this matrix was written: the special-graphics briefing redraw
(ShowLevelBriefing 4566 -> RedrawLevel 394F -> SetupSpecialGraphicsResource 1A7B)
is bound in the host, so Fun 22, Tricky 14, Taxing 15 and Mayhem 22 play; the
host's safety budgets scale with frames, so a scripted run plays a level through
time-up to the result screen.
