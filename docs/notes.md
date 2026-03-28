# Notes

Working assumptions:

- WatchDog remains the source of reviewed truth
- WatchPuppy consumes exported labels and snapshots
- `TEST` runs in WatchDog are evaluation aids, not source-of-truth training data
- live runtime target remains:
  - `failed_get_up_attempt`
- current serving input is:
  - `snapshot_shrink.jpg`
- PicMosaic maintenance policy:
  - online single-event append
  - bulk rebuild as a separate maintenance operation
- RTSP ingest policy:
  - OpenCV backend keeps the RTSP connection open across events when `ingest.persistent_connection` is true
  - live TAPO config currently enables this mode
  - goal is lower snapshot latency after ONVIF `pet` trigger without reintroducing clip capture
  - this improves immediacy, but does not guarantee cross-camera temporal alignment
  - TAPO may still emit `pet` events at different moments per camera for the same real-world scene
- ONVIF pull policy:
  - collector uses explicit SOAP/HTTP operation timeout protection
  - `PullMessages()` failure rebuilds the ONVIF context instead of only resubscribing
  - periodic pull heartbeat logs are used to detect silent stalls
- alert delivery policy:
  - Telegram send is asynchronous
  - default mode is text-only
  - photo mode is opt-in through `WATCHPUPPY_TELEGRAM_SEND_PHOTO`
- operator viewing policy:
  - separate `watchpuppy-stream@*` services expose viewing endpoints
  - current relay backend is `ffmpeg`
  - output format is HTTP MPEG-TS at `/stream.ts`
  - relay/viewing is intentionally independent from the detection pipeline
