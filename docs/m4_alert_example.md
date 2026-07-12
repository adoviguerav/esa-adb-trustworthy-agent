# Example two-moment alert (event 33)

## Moment 1 -- START flag (deterministic, ~bytes, no LLM)

```
ANOMALY START t=2002-12-31T05:13:12 | ch 20,18,19 | intensity high (score 0.002) | conf>0.9999 (saturated)
```

## Moment 2 -- closing alert (audited)

## Anomaly event 33 -- closing brief

### Facts (verbatim from the detection pipeline)

| fact | value (verbatim from M3) |
|---|---|
| event_id | `33` |
| start | `"2002-12-31T05:13:12"` |
| end | `"2003-01-01T12:06:00"` |
| duration_sec | `111168.0` |
| m2_confidence | `0.9999826797838437` |
| priority | `1.4524880522715875` |
| intensity | `0.2878503259019933` |
| localization | `"confident"` |
| dominant_channels | `["channel_18", "channel_23", "channel_22", "channel_21"]` |
| top_channels | `[["channel_18", 31.415393836723307], ["channel_23", 18.42732120995479], ["channel_22", 18.122380519471925], ["channel_21", 17.275987953242492], ["channel_24", 9.02692514818249], ["channel_20", 3.1640469896480043], ["channel_19", 2.567944342777004]]` |

note: m2_confidence saturates (~1 for every flagged event; alpha* floor) -- it does not rank events. Use priority.

### Similar past anomalies (retrieved, all ended before this event)

| past anomaly | similarity | shared channels |
|---|---|---|
| id_638 | 0.898 | channel_18, channel_21, channel_22, channel_23, channel_24 |
| id_326 | 0.800 | channel_18, channel_19, channel_20, channel_21, channel_22, channel_23, channel_24 |
| id_116 | 0.769 | channel_18, channel_19, channel_20, channel_21, channel_22, channel_23, channel_24 |
| id_554 | 0.741 | channel_18, channel_19, channel_20, channel_21, channel_22, channel_23, channel_24 |
| id_405 | 0.714 | channel_18, channel_19, channel_20, channel_21, channel_22, channel_23, channel_24 |

combination novelty: 0.102 (1 = channel set unlike anything in the archive)

### Brief (LLM-generated, audited)

The event is now closed -- the detector stopped flagging windows (says nothing about the underlying issue being resolved). Localization is confident and the dominant channels are channel_18, channel_23, channel_22, and channel_21. All flagged channels include channel_18, channel_23, channel_22, channel_21, channel_24, channel_20, and channel_19. hypothesis (unconfirmed): channel_23, channel_22, channel_21 share group_2 (group); channel_23, channel_22, channel_21 share physical_unit_9 (unit) -- a coupled behaviour is possible. The anomaly persisted for 30 h 52 min 48 s with a confidence of 99.998 %; confidence is saturated (near its ceiling) across ALL flagged events; it does not rank or discriminate between events -- use the priority value in the facts table. The channel combination is familiar; derived deterministically from how much this event's CHANNEL COMBINATION matches past anomalies; it says nothing about magnitude or severity.

