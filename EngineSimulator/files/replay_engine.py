"""
replay_engine.py
=================
Reads a mission file saved by MissionSimulator.save_mission() and replays it.
This module NEVER recomputes physics -- it only looks up stored rows by
time, exactly matching the requirement "replay must read history rather
than regenerate it."

Frontend usage pattern (dashboard calls this every animation frame):

    replay = MissionReplay("demo_mission.json")
    replay.play()
    ...
    while dashboard_running:
        replay.advance(real_dt_seconds)     # call once per frame
        state = replay.current_state()      # dict, or None if before/after mission
        events_this_frame = replay.events_between(prev_t, replay.playhead_s)
        render(state, events_this_frame)
"""

import json
import bisect


class MissionReplay:
    def __init__(self, filepath: str):
        with open(filepath) as f:
            self.data = json.load(f)

        self.mission_name = self.data["mission_name"]
        self.config = self.data["config"]
        self.timeseries = self.data["timeseries"]
        self.events = self.data["events"]
        self.duration_s = self.data["duration_s"]

        self._times = [row["time_s"] for row in self.timeseries]

        self.playhead_s = 0.0
        self.speed = 1.0
        self.is_playing = False

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------
    def play(self):
        self.is_playing = True

    def pause(self):
        self.is_playing = False

    def set_speed(self, multiplier: float):
        """e.g. 1.0 = real-time, 4.0 = 4x fast-forward, 0.5 = half speed."""
        self.speed = max(0.0, multiplier)

    def seek(self, time_s: float):
        self.playhead_s = max(0.0, min(self.duration_s, time_s))

    def advance(self, real_dt_seconds: float):
        """Call once per UI frame with the real (wall-clock) elapsed seconds."""
        if self.is_playing:
            self.playhead_s = min(self.duration_s, self.playhead_s + real_dt_seconds * self.speed)
            if self.playhead_s >= self.duration_s:
                self.is_playing = False

    # ------------------------------------------------------------------
    # Reading stored data -- no recomputation, pure lookup
    # ------------------------------------------------------------------
    def current_state(self):
        return self.state_at(self.playhead_s)

    def state_at(self, time_s: float):
        if not self._times:
            return None
        idx = bisect.bisect_right(self._times, time_s) - 1
        idx = max(0, min(idx, len(self.timeseries) - 1))
        return self.timeseries[idx]

    def events_between(self, t_start: float, t_end: float):
        return [e for e in self.events if t_start < e["time_s"] <= t_end]

    def full_event_timeline(self):
        """All events, for rendering a scrubber/timeline strip in the UI."""
        return self.events

    def stage_boundaries(self):
        """[(stage_name, start_s, end_s), ...] -- handy for drawing stage bands on the timeline."""
        starts = {e["stage"]: e["time_s"] for e in self.events if e["type"] == "stage_start"}
        ends = {e["stage"]: e["time_s"] for e in self.events if e["type"] == "stage_end"}
        return [(name, starts[name], ends[name]) for name in starts if name in ends]


if __name__ == "__main__":
    replay = MissionReplay("demo_mission.json")
    print(f"Loaded mission: {replay.mission_name}")
    print(f"Config: {replay.config}")
    print(f"Duration: {replay.duration_s}s, samples: {len(replay.timeseries)}, events: {len(replay.events)}\n")

    # Simulate a dashboard scrubbing to the middle of the injected fault
    replay.seek(255)
    print("State at t=255s (should show the injected oil-pressure fault):")
    print(replay.current_state())

    # Simulate normal playback for a few frames at 10x speed
    replay.seek(0)
    replay.set_speed(10.0)
    replay.play()
    for _ in range(5):
        replay.advance(real_dt_seconds=1.0)   # 1 real second = 10 sim seconds
        print(f"\nplayhead={replay.playhead_s}s ->", replay.current_state()["stage"])

    print("\nStage boundaries (for the timeline UI):")
    for name, start, end in replay.stage_boundaries():
        print(f"  {name}: {start}s - {end}s")
