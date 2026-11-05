# Korean stock demo / licensed Nasdaq operation separation — 2026-11-06 KST

Owner direction: **retain US Nasdaq-100 code**, but substitute Korean listed shares and KOSPI/KOSDAQ for the demonstration. A real user with the appropriate Nasdaq market-data contractual rights may later enable the US provider after a separate rights, entitlement and publisher-display review. An API token alone is not sufficient.

Local-only Korean stock mode takes `date,stock_close,benchmark_close` CSV (31–501 aligned rows, at most 128 KiB), six-digit Korean ticker, and KOSPI/KOSDAQ selection; computes historical price returns/beta/OLS/R² from source bytes, SHA256 and fail-closed evidence labels. No GET, API key, persistent source storage, external publication, trading, source verification or data-licensing assertion.

This is **not** OpenDART integration, authorized KRX feed, actual DART A/B/C end-to-end, or permission to show original market prices to contest judges. Official KRX API Terms prohibit providing API information to a third party; separate rights check needed for intended display. See https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp and https://opendart.fss.or.kr/intro/main.do .

Existing local-only gate protects the UI; default synthetic demo and SEC/US analysis remain unchanged. Keep internal acceptance score at 76/100 until legitimate real-source gates are satisfied. No payment, live request, provider outreach, Production or contest submission authorized by this patch.
