# Frontend workspace and public dashboard

The UI uses the official Sahayatri logo bundle and brand palette: deep navy
`#1D293D`, teal `#087F75`, light mint `#6ADBC6`, white, and black for
monochrome output. It combines shadcn-inspired primitives, Lucide navigation
icons, and Recharts for public aggregate analytics. All existing API contracts
and backend authorization rules are unchanged.

## Navigation

- `/` shows the public dashboard for visitors and the existing role-specific
  workspace for signed-in users.
- `/public-dashboard` is available without an account. `/transparency`
  redirects here so existing links continue to work.
- Desktop navigation groups reporting, community tools, and safety in a sidebar.
- The desktop sidebar collapses to a persistent icon rail with tooltips.
- Mobile has five primary actions, with the remaining features and display
  preferences in a keyboard-accessible dialog menu.
- Hazard Map & safer routes is citizen-only in both navigation and direct-route
  guards. Authorities are redirected to their workspace.
- The Install app action appears only in the public-page footer. Authenticated
  citizen and authority dashboards do not show installation controls.

## Analytics

The dashboard reads only `/api/public/stats`: all-time report counts, current
status distribution, six highest-volume categories, resolved-this-month count,
median resolution time, and searchable/sortable ward and category tables.
CSV export downloads the currently filtered breakdown. Missing medians and
rates with a zero denominator display a dash. Empty and failed requests keep
account links and refresh available.

Resolution rate is resolved / total reports. The API excludes linked duplicate
reports. No historical trends, priority distributions, or time filters are
invented from the aggregate endpoint. Data is refreshed every minute while the
page is open; the API's generation timestamp is shown.

## Verification

```sh
npm ci
npm run build
npm run lint
npm run test:ui
```

UI tests use the production build, with fixture responses intercepted in the
browser; they do not create accounts or write production data. On Windows they
use installed Microsoft Edge. On other systems run `npx playwright install chromium`
first. Tests cover phone/desktop layouts, charts, export/search, request failure
and retry, empty data, Nepali display preferences, mobile dialog focus, and
authority navigation/search, sidebar persistence, password visibility, and the
citizen-only hazard route. Screenshots are saved under ignored `test-results/`.
