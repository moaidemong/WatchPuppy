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
