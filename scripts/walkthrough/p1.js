// P1 walkthrough (stages 6-8) for the playwright-headless MCP server, chained like a user.
async (page) => {
  const base = 'http://127.0.0.1:8000';
  const out = [];
  const log = (id, ok, note) => out.push(`${id}: ${ok ? 'pass' : 'FAIL'} - ${note}`);
  const t = (n) => page.getByTestId(n);
  const ask = async (q) => {
    const prev = await page.locator('[data-testid=answer-card]').getAttribute('data-run-id').catch(() => null);
    await t('workflow-select').selectOption('auto');
    await t('ask-input').fill(q);
    await t('ask-submit').click();
    await page.waitForFunction((p) => {
      const c = document.querySelector('[data-testid=answer-card]');
      return c && c.getAttribute('data-run-id') && c.getAttribute('data-run-id') !== p;
    }, prev);
  };
  const text = async (n) => (await t(n).first().textContent()).trim();

  await page.request.post(`${base}/api/test/reset`);
  await page.goto(base + '/');
  await ask("Where is SN-0042 and what's blocking it?");
  await t('feedback-down').click();
  const disabledFirst = await t('feedback-submit').isDisabled();
  await t('feedback-reason').selectOption('wrong_data');
  await t('feedback-text').fill('Location looks stale');
  await t('feedback-submit').click();
  await t('feedback-thanks').waitFor();
  await page.goto(base + '/feedback');
  const row = t('feedback-row').first();
  log('E2E-24', disabledFirst && await row.getAttribute('data-status') === 'new' && (await row.textContent()).includes('Wrong data'), 'thumbs-down -> New, Wrong data');

  for (const [status, disp] of [['triaged', 'data_issue'], ['fixed', null], ['verified', null]]) {
    const r = t('feedback-row').first();
    await r.getByTestId('feedback-status-select').selectOption(status);
    if (disp) await r.getByTestId('feedback-disposition-select').selectOption(disp);
    await r.getByTestId('feedback-save').click();
    await page.waitForSelector(`[data-testid=feedback-row][data-status=${status}]`);
  }
  await page.reload();
  log('E2E-25', await t('feedback-row').first().getAttribute('data-status') === 'verified' && await t('feedback-event').count() === 3, '3 events after reload');

  const fid = await t('feedback-row').first().getAttribute('data-feedback-id');
  await t('feedback-row').first().getByTestId('feedback-convert').click();
  await t('feedback-convert-result').waitFor();
  await page.goto(base + '/evals');
  await t('evals-run-mock').click();
  await page.waitForFunction(() => document.querySelector('[data-testid=eval-status]')?.textContent.trim() === 'complete', null, { timeout: 90000 });
  const draft = page.locator(`[data-testid=eval-case-row][data-case-id=draft-${fid}]`);
  log('E2E-26', await draft.getAttribute('data-passed') === 'true' && await text('eval-pass-count') === '60/60', `draft-${fid} passed, suite ${await text('eval-pass-count')}`);

  await page.goto(base + '/');
  const p1 = [['Trace requirement REQ-118', 'requirement_trace'], ["What's the impact of moving P-1077 to rev D?", 'revision_impact'],
              ['Show the scorecard for Apex Castings', 'supplier_scorecard'], ["What's the cycle time for P-2001?", 'cycle_time'],
              ['Shortage report for P-1077', 'shortage_report'], ['Which export-controlled parts are in P-2001?', 'export_check']];
  const chips = [];
  for (const [q, chip] of p1) {
    await ask(q);
    chips.push(`${await text('workflow-chip')}=${await text('decision-badge')}`);
    if (await text('workflow-chip') !== chip || await text('decision-badge') !== 'Answered') break;
  }
  log('E2E-27', chips.length === 6 && chips.every((c) => c.endsWith('=Answered')), chips.join(', '));

  await page.request.post(`${base}/api/test/seed-activity`);
  await page.goto(base + '/dashboard');
  const cell = (panel, key) => page.locator(`[data-testid=dash-panel][data-panel=${panel}] [data-key='${key}']`).textContent();
  const mix = [await cell('decision-mix', 'answered'), await cell('decision-mix', 'declined'), await cell('decision-mix', 'blocked')].join('/');
  log('E2E-30', mix === '14/4/2' && (await cell('eval-pass-rate', 'latest')).trim() === '30/30' && (await cell('drift-incidents', 'total')).trim() === '2', `mix ${mix}`);
  await page.screenshot({ path: 'test-results/dashboard.png', fullPage: true });
  await page.request.post(`${base}/api/test/reset`);
  return out.join('\n');
}
