# mneme-verify — clean-room Go verifier

Second, spec-only implementation of `mneme-cf-bundle/v1`
verification. Written against `../spec/cf-bundle-v1.md` and the
`../conformance/cf/v1/` corpus WITHOUT reading the producing
codebase — that independence is the point: shared assumptions fail
together, separate transcriptions have to be argued into agreement
by the spec.

Build:  `go build -buildvcs=false -o mneme-verify .`
Run:    `./mneme-verify <bundle-or-envelope> [trusted-keys.json]`
Canon:  `./mneme-verify --canon < input.json` (differential driver)

Agreement with the Python reference is proven by
`../conformance/cf/v1/differential.sh` — identical verdicts on every
artifact, including identical rejections on every mutant.
