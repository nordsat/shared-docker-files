# pytroll-chain

## Building

From main directory run

`docker buildx build --network=host --tag segment_gatherer:latest segment_gatherer/`
`docker buildx build --network=host --tag posttroll:latest posttroll/`
`docker buildx build --network=host --tag trollflow2:latest trollflow2/`
`docker buildx build --network=host --tag trollstalker:latest trollstalker/`

## Running

Still in pytroll-chain main directory run:

`docker compose up`
