# deepsense/reactor-meltdown

The agent reconstructs the causal propagation order of a partial reactor
meltdown across five subsystems (COOLING, PRIMARY_LOOP, CORE, STEAM_GEN,
TURBINE) from 48 hours of sensor logs split across three monitoring systems
(see [instruction.md](instruction.md)). The catch: onset means when the
*physical state* first deviated — loggers record in different local time
zones (`logger_utc_offset_hours`), every sensor has a response delay to
subtract, phantom glitches must be separated from the real cascade, and
readings saturate at a plateau, so the true onset must be back-extrapolated
from the pre-saturation trend. The answer is the ordered list of all five
subsystem names.

## Details

Physical onset order by Dijkstra over the propagation graph:
CORE(1440) -> PRIMARY_LOOP(1460) -> STEAM_GEN(1485)
-> COOLING(1505) -> TURBINE(1520)

Seven traps embedded in the data:

0. Timezone mismatch (Trap — new primary difficulty).
   The three sensor files come from independent monitoring systems
   with different local clocks: sensors_01.csv (COOLING,
   PRIMARY_LOOP) is UTC+0, sensors_02.csv (CORE, STEAM_GEN) is
   UTC+2, sensors_03.csv (TURBINE) is UTC-1.  Timestamps are
   written without timezone suffix.  A model that naively
   pd.concat + pd.to_datetime without normalising to UTC sees
   CORE readings shifted +2 h and TURBINE readings shifted −1 h
   relative to their true UTC time.  After regression
   extrapolation, the naïve onset order becomes roughly
   TURBINE ≈ PRIMARY_LOOP < COOLING < CORE < STEAM_GEN —
   the opposite of the correct order.  The fix: read
   logger_utc_offset_hours from sensor_metadata.csv and subtract
   it from each reading's timestamp before any analysis.

1. Sensor response delay (Trap).  Each sensor has an inherent lag
   (0-8 min) before a physical change appears in its reading.  A
   fast pressure sensor (delay=0) in a downstream subsystem can
   report an anomaly before a slow thermocouple (delay=8) in an
   upstream subsystem, inverting the naive "first anomaly wins"
   ordering.  The solution subtracts response_delay_minutes from
   each observed timestamp before comparing onset times.

2. Phantom glitches (Trap).  Three sensors spike briefly before or
   shortly after the real cascade begins, each staying above the
   operating limit for fewer than 30 consecutive minutes:
  - TURB_OUTPUT_01 at hour 18 (minute 1080), 25 min — clearly
    pre-cascade, but long enough to look like an early event.
  - STEAM_PRES_01 at hour 20 (minute 1200), 20 min — also
    pre-cascade.
  - COOLING_PRES_01 at minute 1450, 25 min — this glitch starts
    10 minutes AFTER the real cascade begins (minute 1440) and
    ends 55 minutes before COOLING's true onset (minute 1505).
    Its delay-corrected timestamp precedes CORE's first real
    alarm by hours, making COOLING look like the root cause to
    any model that uses first-alarm ordering (even after
    filtering pre-cascade events).
    The correct fix: require at least 30 minutes of sustained
    out-of-range readings in a 60-minute window before declaring
    an onset; none of the phantom glitches qualify.

3. Alarm lag (Trap).  Alarms fire when sensor values cross hard
   thresholds (30 % of normal range past the operating limit).
   This happens hundreds of minutes after the anomaly begins its
   gradual rise.  Alarm order therefore reflects threshold-crossing
   time, not onset time.  The operator action timestamps and alarm
   timestamps give the wrong causal sequence if used directly.

4. Operator suppression dip (Trap).  Each time a CRITICAL alarm
   fires for a subsystem, an operator intervenes 10–30 min later
   and temporarily suppresses the anomaly by 30–50 % for 10–20
   min.  A detector that resets on any return to the normal band
   will misidentify the post-suppression resumption as the true
   onset.  The correct algorithm looks through dips: the onset is
   the first sustained deviation, regardless of later suppressions.

5. TURBINE/STEAM_GEN correlated noise (Trap).  These two subsystems
   share a mechanical coupling that correlates their sensor noise
   even during normal operation.  Naive cross-correlation analysis
   sees a strong zero-lag correlation between TURBINE and STEAM_GEN
   and cannot determine which was affected first.  The correct
   approach uses the magnitude of the growing deviation trend (which
   subsystem's readings drifted outward first), not correlation lag.

6. Asymmetric deterioration rates (Trap — primary difficulty).
   Each subsystem degrades at a different rate: TURBINE (last
   affected, onset minute 1520) deteriorates 15× faster than CORE
   (root cause, onset minute 1440).  As a result, TURBINE's sensors
   cross the operating limit ~42 minutes after its onset, while
   CORE's sensors cross ~625 minutes after its onset.  Any
   threshold-based approach — first OOR reading, first alarm,
   first sustained OOR cluster — ranks subsystems by how fast they
   degrade, not by when they started.  This produces approximately
   the reversed causal order: TURBINE -> COOLING -> STEAM_GEN ->
   PRIMARY_LOOP -> CORE.
   The correct fix: fit a linear regression through the
   pre-saturation OOR readings for each sensor, back-extrapolate
   the trend to the sensor's normal-range centre, and use that
   extrapolated minute as the true physical onset.  This recovers
   the onset time independently of deterioration rate.
   Growth rates (deviation_fraction per minute): CORE 0.0008,
   PRIMARY_LOOP 0.0016, STEAM_GEN 0.003, COOLING 0.006,
   TURBINE 0.012.
