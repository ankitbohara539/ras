import { test, expect, type Page } from '@playwright/test'

const stats = {
  municipality_code: 'KMC',
  municipality_name_en: 'Kathmandu Metropolitan City',
  municipality_name_ne: 'काठमाडौं महानगरपालिका',
  total_tickets: 240,
  open_tickets: 72,
  resolved_tickets: 156,
  resolved_this_month: 24,
  median_resolution_hours: 38.4,
  generated_at: '2026-09-19T09:00:00Z',
  by_ward: [
    {
      number: 5,
      name_en: 'Hadigaun',
      name_ne: 'हाडीगाउँ',
      total: 140,
      open: 50,
      resolved: 80,
      median_resolution_hours: 24,
    },
    {
      number: 10,
      name_en: 'Baneshwor',
      name_ne: 'बानेश्वर',
      total: 100,
      open: 22,
      resolved: 76,
      median_resolution_hours: 48,
    },
  ],
  by_category: [
    'Road maintenance',
    'Street lighting',
    'Water supply',
    'Waste management',
    'Drainage',
    'Public sanitation',
  ].map((name, i) => ({
    key: String(i),
    name_en: name,
    name_ne: name,
    total: 65 - i * 10,
    resolved: 41 - i * 6,
    median_resolution_hours: i ? 36 : null,
  })),
}
async function mockApi(
  page: Page,
  authenticated = false,
  role = 'citizen',
  notificationItems: Record<string, unknown>[] = [],
) {
  await page.addInitScript(
    ({ authenticated }) => {
      localStorage.setItem('sahayatri.language', 'en')
      localStorage.setItem('sahayatri.install-dismissed', '1')
      if (authenticated)
        localStorage.setItem('sahayatri.access_token', 'ui-test-token')
    },
    { authenticated },
  )
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    let json: unknown = {}
    if (path === '/api/public/stats') json = stats
    else if (path === '/api/users/me')
      json = {
        id: 'ui-test',
        full_name: 'Ankit Bohara',
        role,
        account_status: 'active',
      }
    else if (path === '/api/notifications')
      json = {
        unread: notificationItems.filter((item) => !item.read_at).length,
        items: notificationItems,
      }
    else if (path === '/api/hazards') json = { items: [], night: false }
    else if (path === '/api/geo/search') json = []
    else if (path === '/api/tickets') json = { total: 0, items: [] }
    else if (
      ['/api/alerts', '/api/sos', '/api/tickets/review/queue'].includes(path)
    )
      json = []
    return route.fulfill({ json })
  })
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true)
}
for (const width of [390, 1440]) {
  test(`public dashboard at ${width}px: charts, account links, filtering and export`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 960 })
    await mockApi(page)
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'Small reports. Visible progress.' }),
    ).toBeVisible()
    await expect(
      page.getByRole('link', { name: 'Sign in', exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('link', { name: 'Create account', exact: true }).first(),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Install app' })).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Install app' }).locator('img'),
    ).toHaveAttribute('src', '/icon-192.png')
    await expect(page.locator('.recharts-surface')).toHaveCount(2)
    await page.locator('.recharts-bar-rectangle').first().hover()
    await expect(page.getByTestId('ward-chart-tooltip')).toContainText('Ward 5')
    await expect(page.getByTestId('ward-chart-tooltip')).toContainText('Hadigaun')
    await expect(
      page.getByRole('rowheader', { name: 'Ward 5', exact: false }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'By category', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Show more' })).toBeVisible()
    await expect(page.getByRole('row')).toHaveCount(6)
    await page.getByRole('button', { name: 'Show more' }).click()
    await expect(page.getByRole('row')).toHaveCount(7)
    await page.getByRole('textbox', { name: 'Search breakdown' }).fill('Street')
    await expect(page.getByRole('row')).toHaveCount(2)
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export CSV' }).click()
    expect((await downloadPromise).suggestedFilename()).toContain(
      'categories.csv',
    )
    await page.getByRole('textbox', { name: 'Search breakdown' }).fill('')
    await noOverflow(page)
    expect(errors).toEqual([])
    await page.screenshot({
      path: testInfo.outputPath('public-dashboard.png'),
      fullPage: true,
    })
    await page.getByRole('link', { name: 'Sign in', exact: true }).click()
    await expect(
      page.getByRole('textbox', { name: 'Email', exact: false }),
    ).toBeVisible()
    await noOverflow(page)
  })
}
test('mobile navigation: drawer, keyboard focus and public dashboard', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page, true)
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Welcome back, Ankit' }),
  ).toBeVisible()
  await expect(
    page
      .getByRole('navigation', { name: 'Primary navigation' })
      .getByRole('link'),
  ).toHaveCount(5)
  await page.getByRole('button', { name: 'Menu', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(
    page.getByRole('dialog').getByRole('link', { name: 'Public dashboard' }),
  ).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Menu', exact: true }),
  ).toBeFocused()
  await noOverflow(page)
  await page.screenshot({
    path: testInfo.outputPath('citizen-mobile.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Menu', exact: true }).click()
  await page
    .getByRole('dialog')
    .getByRole('link', { name: 'Public dashboard' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Small reports. Visible progress.' }),
  ).toBeVisible()
})
test('API error keeps account links and retry recovers', async ({ page }) => {
  await mockApi(page)
  await page.route('**/api/public/stats', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Temporarily unavailable' } }),
  )
  await page.goto('/public-dashboard')
  await expect(page.getByRole('alert')).toContainText('Temporarily unavailable')
  await expect(
    page.getByRole('link', { name: 'Sign in', exact: true }),
  ).toBeVisible()
  await page.unroute('**/api/public/stats')
  await page.getByRole('button', { name: 'Refresh data' }).click()
  await expect(page.locator('.recharts-surface')).toHaveCount(2)
})
test('empty data, legacy URL and Nepali accessibility', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.route('**/api/public/stats', (route) =>
    route.fulfill({
      json: {
        ...stats,
        total_tickets: 0,
        open_tickets: 0,
        resolved_tickets: 0,
        resolved_this_month: 0,
        median_resolution_hours: null,
        by_ward: [],
        by_category: [],
      },
    }),
  )
  await page.goto('/transparency')
  await expect(page).toHaveURL(/public-dashboard/)
  await expect(page.getByText('Your community story starts here')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
  await page
    .getByRole('button', { name: 'Large text', exact: true })
    .last()
    .click()
  await page
    .getByRole('button', { name: 'High contrast', exact: true })
    .last()
    .click()
  await page
    .getByRole('button', { name: 'भाषा / Language', exact: true })
    .last()
    .click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'ne')
  await noOverflow(page)
})
test('authority workspace: queues and report search', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockApi(page, true, 'admin')
  await page.goto('/')
  await expect(page).toHaveURL(/authority/)
  await expect(
    page.getByRole('textbox', { name: 'Search reports' }),
  ).toBeVisible()
  await expect(
    page.locator('aside').getByRole('link', { name: 'Public dashboard' }),
  ).toBeVisible()
  await expect(
    page.locator('aside').getByRole('button', { name: 'Install app' }),
  ).toHaveCount(0)
  await expect(
    page.locator('aside').getByRole('link', { name: 'Hazard map' }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: 'Collapse sidebar' }).click()
  await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()
  const request = page.waitForRequest((r) => r.url().includes('search=pothole'))
  await page.getByRole('textbox', { name: 'Search reports' }).fill('pothole')
  await request
  await noOverflow(page)
  await page.screenshot({
    path: testInfo.outputPath('authority-desktop.png'),
    fullPage: true,
  })
})

test('password controls are accessible and reveal on demand', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')
  const password = page.locator('input[autocomplete="current-password"]')
  await expect(password).toHaveAttribute('type', 'password')
  await page.getByRole('button', { name: 'Show password' }).click()
  await expect(password).toHaveAttribute('type', 'text')
  await expect(page.getByRole('button', { name: 'Hide password' })).toBeVisible()
})

test('hazard map route is citizen-only, including direct navigation', async ({
  page,
}) => {
  await mockApi(page, true, 'admin')
  await page.goto('/safe-route')
  await expect(page).toHaveURL(/\/authority$/)
  await expect(page.getByRole('textbox', { name: 'Search reports' })).toBeVisible()
})

test('safer route Point B shows loading, a bounded address and issue-specific markers', async ({
  page,
}) => {
  await mockApi(page, true)
  await page.route('**/api/hazards**', (route) =>
    route.fulfill({
      json: {
        night: false,
        items: [
          {
            id: 'flood-1',
            source: 'ticket',
            kind: 'flooding',
            title: 'Flooded street near the junction',
            severity: 'high',
            latitude: 27.7172,
            longitude: 85.324,
            radius_m: 40,
            modes: ['walk', 'wheelchair', 'drive'],
            night_only: false,
            active_now: true,
            avoid: true,
            approximate: false,
            reported_at: '2026-09-19T08:00:00Z',
            reports: 3,
            confirmations: 1,
            ticket_id: null,
            alert_id: null,
            category_key: 'waterlogging',
          },
        ],
      },
    }),
  )
  await page.route('**/api/geo/search**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.fulfill({
      json: [
        {
          name: 'Ratna Park',
          display_name:
            'Ratna Park, Bagbazar, Ward 28, Kathmandu Metropolitan City, Bagmati Province, Nepal',
          latitude: 27.7066,
          longitude: 85.3157,
        },
      ],
    })
  })

  await page.goto('/safe-route')
  await page.getByRole('searchbox', { name: 'To' }).fill('Ratna Park')
  await expect(page.getByText('Searching places…')).toBeVisible()
  await page.getByRole('button', { name: /Ratna Park/ }).click()

  const destination = page.getByTestId('destination-summary')
  await expect(destination).toContainText('Ratna Park')
  const address = destination.getByText(/Kathmandu Metropolitan City/)
  await expect(address).toBeVisible()
  await expect(address).toHaveClass(/line-clamp-3/)
  await expect(page.locator('.hazard-icon').first()).toContainText('≋')
})

test('notifications can be filtered by all, unread and read', async ({ page }) => {
  await mockApi(page, true, 'citizen', [
    {
      id: 'notification-unread',
      type: 'ticket_update',
      title_en: 'Your report is being reviewed',
      title_ne: 'तपाईंको उजुरी समीक्षा हुँदैछ',
      body_en: 'Ward staff started reviewing your report.',
      ticket_id: null,
      alert_id: null,
      read_at: null,
      created_at: '2026-09-19T08:00:00Z',
    },
    {
      id: 'notification-read',
      type: 'ticket_update',
      title_en: 'Your report was resolved',
      title_ne: 'तपाईंको उजुरी समाधान भयो',
      body_en: 'The repair team completed the work.',
      ticket_id: null,
      alert_id: null,
      read_at: '2026-09-19T09:00:00Z',
      created_at: '2026-09-19T07:00:00Z',
    },
  ])
  await page.goto('/notifications')

  await expect(page.getByText('Your report is being reviewed')).toBeVisible()
  await expect(page.getByText('Your report was resolved')).toBeVisible()
  const filters = page.getByRole('group', { name: 'Filter notifications' })

  await filters.getByRole('button', { name: /^Unread/ }).click()
  await expect(page.getByText('Your report is being reviewed')).toBeVisible()
  await expect(page.getByText('Your report was resolved')).not.toBeVisible()

  await filters.getByRole('button', { name: /^Read/ }).click()
  await expect(page.getByText('Your report was resolved')).toBeVisible()
  await expect(page.getByText('Your report is being reviewed')).not.toBeVisible()

  await filters.getByRole('button', { name: /^All/ }).click()
  await expect(page.getByText('Your report is being reviewed')).toBeVisible()
  await expect(page.getByText('Your report was resolved')).toBeVisible()
})
