from collections import deque
import flet as ft
import flet_audio_recorder as far
import numpy as np


SAMPLE_RATE = 44100
CHANNELS = 1
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MIN_FREQ = 70
MAX_FREQ = 350

def get_note(pitch):
    a4 = 440.0
    midi = round(69 + 12 * np.log2(pitch / a4))
    note = NOTES[midi % 12]
    octave = midi // 12 - 1
    note_pitch = a4 * 2 ** ((midi - 69) / 12)
    cents = 1200 * np.log2(pitch / note_pitch)
    return note, octave, round(cents)

def detect_pitch(samples, sample_rate):
    samples = samples.astype(np.float32)

    rms = np.sqrt(np.mean(samples ** 2))
    
    if rms < 200:
        return None

    samples -= np.mean(samples)
    samples *= np.hanning(len(samples))

    corr = np.correlate(samples, samples, mode="full")
    corr = corr[len(corr) // 2:]

    if corr[0] == 0:
        return None

    corr /= corr[0]
    corr[0] = 0

    min_lag = int(sample_rate / MAX_FREQ)
    max_lag = int(sample_rate / MIN_FREQ)
    lag = np.argmax(corr[min_lag:max_lag]) + min_lag

    return sample_rate / lag if corr[lag] > 0.4 else None

def main(page: ft.Page):
    page.window.width = 300
    page.window.height = 400
    page.title = "Guitar Tuner"
    page.appbar = ft.AppBar(title=ft.Text("Guitar Tuner"), center_title=True)
    note = ft.Text("/", size=100, data=0)
    cents = ft.Text("Cents: /", size=50, data=0)

    window_size = 200
    window_samples = SAMPLE_RATE * window_size // 1000
    buffer = deque(maxlen=window_samples)
    pitch_buffer = deque(maxlen=10)

    def show_snackbar(message):
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    async def handle_start_recording():
        try:
            status = await recorder.has_permission()

            if not status:
                show_snackbar("App requires microphone permission")
                return

            await recorder.start_recording(
                configuration=far.AudioRecorderConfiguration(
                    encoder=far.AudioEncoder.PCM16BITS,
                    sample_rate=SAMPLE_RATE,
                    channels=CHANNELS
                )
            )
        except:
            show_snackbar(f"Error checking microphone permission")

    def handle_stream(e: far.AudioRecorderStreamEvent):
        samples = np.frombuffer(e.chunk, dtype=np.int16)
        buffer.extend(samples)
        
        if len(buffer) == buffer.maxlen:
            window = np.array(buffer, dtype=np.int16)
            pitch = detect_pitch(window, SAMPLE_RATE)

            if pitch is None:
                pitch_buffer.clear()
                note.value = "/"
                note.color = "white"
                cents.value = "Cents: /"
            else:
                pitch_buffer.append(pitch)

                if len(pitch_buffer) == pitch_buffer.maxlen:
                    note_, octave, cents_ = get_note(np.median(pitch_buffer))
                    note.value = f"{note_}{octave}"
                    note.color = "green" if abs(cents_) < 5 else "red"
                    cents.value = f"Cents: {f"+{cents_}" if cents_ > 0 else cents_}"

    async def handle_lifecycle_state_change(e: ft.AppLifecycleStateChangeEvent):
        if e.state in [ft.AppLifecycleState.DETACH, ft.AppLifecycleState.HIDE, ft.AppLifecycleState.INACTIVE, ft.AppLifecycleState.PAUSE] \
            and page.platform.value.lower() == "android":

            if await recorder.is_recording():
                await recorder.stop_recording()
        else:
            if not (await recorder.is_recording()):
                await handle_start_recording()

    page.on_app_lifecycle_state_change = handle_lifecycle_state_change

    recorder = far.AudioRecorder(on_stream=handle_stream)

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=note,
                        alignment=ft.Alignment.CENTER,
                        border=ft.Border(ft.BorderSide())
                    ),
                    ft.Container(
                        content=cents,
                        alignment=ft.Alignment.CENTER,
                        border=ft.Border(ft.BorderSide()),
                        padding=ft.Padding(0, 20, 0, 0)
                    )
                ]
            )
        )
    )

    page.run_task(handle_start_recording)


ft.run(main)
