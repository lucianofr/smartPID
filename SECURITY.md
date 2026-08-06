# Security Policy

smartPID is an edge process-control platform: the backend talks OPC-UA to
industrial controllers and the web app exposes live loop data. Treat it as
operational infrastructure.

## Supported Versions

Only the current `main` branch receives security fixes. Tagged releases are
supported until the next release ships.

## Reporting a Vulnerability

Do **not** open a public issue for security defects. Report privately:

- GitHub: use the repository's *Security → Report a vulnerability* flow
  (private vulnerability reporting).
- Email: `luciano82@gmail.com` with `[smartPID-security]` in the subject.

Include, when available:

1. Affected component and version/commit.
2. Steps to reproduce (no live credentials).
3. Impact assessment — especially anything reachable from the network.
4. Suggested fix, if you have one.

You will get an acknowledgement within 72 h and a fix timeline once the
report is triaged.

## Secrets Handling

- `.env` and `*.local` secrets are gitignored — never commit OPC-UA
  credentials, tokens, or private keys.
- `.env.example` is the only checked-in environment template and must stay
  placeholder-only.
- Anyone rotating a credential (OPC-UA user, OPC-UA server certificate,
  web session secret) must rotate it in the deployment (Dokploy/Docker) and
  locally — never via git history.

## Deployment Notes

- The web UI is served behind the reverse proxy in `docker-compose.yml`;
  keep TLS termination there and do not expose raw OPC-UA ports publicly.
- New OPC-UA endpoints are validated client-side and must keep the
  `opc.tcp://` scheme check (see the OPC-UA connection tests).
