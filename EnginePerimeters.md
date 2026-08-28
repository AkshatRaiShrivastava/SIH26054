These are the following perimeters on which our engine health/performance will depend.

Explanation of  each and info about normal and abnormal scanerios:

The 11 parameters

1. RPM (Revolutions Per Minute)
 What it is: engine rotational speed. The baseline driver
almost everything else scales against.

•  Normal: cruise RPM typically sits in a defined band
the engine is rated for (e.g., mid-range for a small
aero piston engine); climb/high-power phases run
higher.

•  Abnormal: erratic fluctuation (surging) suggests fuel

delivery or ignition problems; inability to reach
commanded RPM suggests power loss.

2. CHT — Cylinder Head Temperature
 What it is: temperature at the cylinder head, the single
most-watched health parameter in piston aero engines.

•  Normal: a defined safe band (too cold = incomplete

combustion/wear; too hot = detonation risk).

•  Abnormal: rapid rise = detonation, cooling failure, or
over-lean mixture; one cylinder reading high vs.
others = localized fault (stuck valve, bad plug).

3. EGT — Exhaust Gas Temperature
 What it is: temperature of exhaust gases leaving the
cylinder, used alongside CHT to infer mixture and
combustion quality.

•  Normal: tracks predictably with RPM/throttle and

fuel-air mixture.

•  Abnormal: sudden spike = lean condition or pre-

ignition; sudden drop = misfire (cylinder not firing)
— this is a textbook misfire signature.

4. Oil Pressure & Oil Temperature
 What it is: lubrication system health — oil pressure
keeps moving parts from grinding metal-on-metal; oil
temp reflects both engine heat and lubrication
efficiency.

•  Normal: pressure stable within a defined range

across RPM; temp rises gradually to a steady-state
operating range.

•  Abnormal: pressure dropping over time =

developing leak or pump wear (your worked
example in the execution plan); pressure oscillating
= air in the system or failing pump; temp climbing
without pressure change = cooling or viscosity
breakdown.

5. Fuel Flow
 What it is: rate of fuel consumption, should correlate
tightly with RPM/power setting.

•  Normal: predictable curve vs. RPM and altitude

(thinner air at altitude changes mixture
requirements).

•  Abnormal: flow not matching expected value for

RPM = injector fault, blockage, or fuel system leak.

6. Vibration Signatures
 What it is: mechanical vibration amplitude/frequency
pattern — arguably the earliest warning sign of many
mechanical faults before temperature/pressure
parameters shift at all.

•  Normal: low, stable baseline amplitude at a given

RPM.

•  Abnormal: rising amplitude = bearing wear,

propeller imbalance, or mount fatigue; specific
frequency signatures can indicate which
component (this is genuinely a deep field —
vibration signature analysis is its own discipline in
industrial predictive maintenance).

7. Battery/Alternator Health
 What it is: electrical system status — critical because
FADEC, sensors, and ignition often depend on stable
electrical supply.

•  Normal: voltage stable in expected range under

load.

•  Abnormal: voltage sag under load = failing

alternator or battery degradation; this cascades to
unreliable sensor readings elsewhere, which is an
interesting complexity you could mention
(electrical fault masquerading as sensor fault).

8. Injection Timing Parameters
 What it is: precise timing of fuel injection relative to
piston position — affects combustion efficiency and is
usually FADEC-controlled.

•  Normal: timing tracks a defined schedule vs.

RPM/load.

•  Abnormal: drift from commanded timing = actuator
wear or FADEC calibration fault; directly causes
misfire/combustion-instability symptoms.

How to get realistic data for all of these

You won't find DRDO's actual numbers — and you
don't need to. Use this three-source approach:

1. Public general-aviation reference ranges —

Lycoming/Continental engine operating manuals
and pilot-training materials publish normal
operating ranges for CHT, EGT, oil temp/pressure
for small aero piston engines. These are publicly
available (owner's manuals, FAA/EASA general
aviation training materials, engine monitor product
documentation like JPI/Garmin engine monitors
used in light aircraft). Use these as your baseline
"normal" ranges — you're not claiming they're
DRDO's exact numbers, just a credible, cited
starting point.

2. Automotive/industrial predictive-maintenance
literature for fault signatures — how a parameter
drifts during a developing fault (the shape of decay,

not the exact numbers) is well documented in
general condition-based-maintenance research,
since the failure physics (bearing wear, lubrication
breakdown, combustion instability) isn't
aerospace-exclusive.

