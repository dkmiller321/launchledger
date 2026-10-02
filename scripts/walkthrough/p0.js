// P0 walkthrough (stages 0-5) for the playwright-headless MCP server, chained like a user.
// Run with browser_run_code_unsafe { filename: "scripts/walkthrough/p0.js" } against :8000.
async (page) => {
  const base = 'http://127.0.0.1:8000';
  const out = [];
  const log = (id, ok, note) => out.push(`${id}: ${ok ? 'pass' : 'FAIL'} - ${note}`);
  const t = (n) => page.getByTestId(n);
  const ask = async (q, wf = 'auto') => {
    const prev = await page.locator('[data-testid=answer-card]').getAttribute('data-run-id').catch(() => null);
    await t('workflow-select').selectOption(wf);
    await t('ask-input').fill(q);
    await t('ask-submit').click();
    await page.waitForFunction((p) => {
      const c = document.querySelector('[data-testid=answer-card]');
      return c && c.getAttribute('data-run-id') && c.getAttribute('data-run-id') !== p;
    }, prev);
    return page.locator('[data-testid=answer-card]').getAttribute('data-run-id');
  };
  const badge = async () => (await t('decision-badge').textContent()).trim();

  await page.request.post(`${base}/api/test/reset`);
  const health = await (await page.request.get(`${base}/healthz`)).json();
  await page.goto(base + '/');
  log('E2E-00', health.db && health.llm_mode === 'mock' && await t('nav-dashboard').isVisible(), JSON.stringify(health));

  await page.goto(`${base}/records/mes/serial/SN-0042`);
  log('E2E-01', (await page.locator('[data-testid=record-field][data-field=status]').textContent()).includes('IN_BUILD'), 'SN-0042 IN_BUILD');

  await page.goto(base + '/');
  const run1 = await ask("Where is SN-0042 and what's blocking it?");
  const cites = await t('citation').count();
  log('E2E-04', await badge() === 'Answered' && cites === 6, `run ${run1}, ${cites} citations, chip ${(await t('workflow-chip').textContent()).trim()}`);
  await page.locator('[data-testid=citation][data-field=status][href$="WO-50102"]').click();
  log('E2E-04b', (await page.locator('[data-testid=record-field][data-field=status]').textContent()).includes('BLOCKED'), 'citation opens WO-50102 BLOCKED');
  await page.goBack();
  await page.goto(`${base}/runs/${run1}`);
  const llm = await page.locator('[data-testid=trace-step][data-kind=llm]').count();
  const tool = await page.locator('[data-testid=trace-step][data-kind=tool]').count();
  log('E2E-05', llm === 4 && tool === 2, `${llm} llm, ${tool} tool steps`);

  await page.goto(base + '/');
  await ask("What's the status of PO-10233 and is it late?", 'po_status');
  log('E2E-06', (await t('workflow-chip').textContent()).trim() === 'po_status (manual)', 'manual chip');
  await ask("What's the weather in Seattle?");
  log('E2E-09', await badge() === 'Declined' && !(await t('answer-text').count()), (await t('decision-reason').textContent()).trim());

  for (const [id, q, rule] of [['E2E-12', 'ghost serial test', 'ids_exist'], ['E2E-13', 'wrong status test', 'facts_match_source'],
                               ['E2E-14', 'uncited claim test', 'citation_required'], ['E2E-15', 'inducer details test', 'export_control']]) {
    await ask(q);
    const reason = (await t('decision-reason').textContent()).trim();
    log(id, await badge() === 'Blocked' && reason.includes(rule) && !(await page.content()).includes('11.5'), reason);
  }
  await ask('Where is SN-0404?');
  log('E2E-16', await badge() === 'Answered' && (await t('caveat').count()) === 1, 'caveated answer');
  await ask('repairable output test');
  log('E2E-17', await badge() === 'Answered', 'repaired');

  await page.goto(base + '/evals');
  await t('evals-run-mock').click();
  await page.waitForFunction(() => document.querySelector('[data-testid=eval-status]')?.textContent.trim() === 'complete', null, { timeout: 90000 });
  log('E2E-18', (await t('eval-pass-count').textContent()).trim() === '30/30', `pass ${(await t('eval-pass-count').textContent()).trim()}`);

  // Core promise, E2E-21
  const apex = 'Which open work orders are at risk from late POs from Apex Castings?';
  await page.goto(base + '/');
  await ask(apex);
  const before = await badge();
  await page.goto(base + '/drift');
  await page.locator('[data-testid=drift-scenario-toggle][data-scenario=erp_rename_promised_date]').check();
  await page.waitForTimeout(500);
  await page.goto(base + '/');
  await ask(apex);
  const reason = (await t('decision-reason').textContent()).trim();
  await page.goto(base + '/drift');
  const erp = await page.locator('[data-testid=drift-system-status][data-system=erp]').getAttribute('data-status');
  const row = page.locator('[data-testid=incident-row][data-field=promised_date][data-status=open]');
  const affected = (await row.getByTestId('incident-runs-affected').textContent()).trim();
  await page.goto(base + '/evals');
  await t('evals-drift-select').selectOption('erp_rename_promised_date');
  await t('evals-run-mock').click();
  await page.waitForFunction(() => document.querySelector('[data-testid=eval-status]')?.textContent.trim() === 'complete', null, { timeout: 90000 });
  const wrong = (await t('eval-wrong-count').textContent()).trim();
  const declined = (await t('eval-declined-count').textContent()).trim();
  await page.goto(base + '/drift');
  await page.locator('[data-testid=drift-scenario-toggle][data-scenario=erp_rename_promised_date]').uncheck();
  await page.waitForTimeout(500);
  await page.locator('[data-testid=incident-row][data-status=open]').first().getByTestId('incident-resolve').click();
  await page.waitForTimeout(500);
  await page.goto(base + '/');
  await ask(apex);
  const after = await badge();
  log('E2E-21', before === 'Answered' && reason.includes('ERP') && reason.includes('promised_date') && erp === 'red'
      && affected === '1' && wrong === '0' && Number(declined) >= 1 && after === 'Answered',
      `before=${before} | ${reason} | erp=${erp} affected=${affected} | drift eval wrong=${wrong} declined=${declined} | after=${after}`);

  await page.goto(base + '/drift');
  await page.locator('[data-testid=drift-scenario-toggle][data-scenario=erp_cost_in_cents]').check();
  await page.waitForTimeout(500);
  await page.goto(base + '/');
  await ask("What's the status of PO-10233 and is it late?");
  const silent = await badge();
  await page.goto(base + '/drift');
  await t('drift-check-now').click();
  await page.waitForTimeout(800);
  const dist = await page.locator('[data-testid=incident-row][data-kind=distribution][data-field=unit_cost_usd]').count();
  await page.goto(base + '/');
  await ask("What's the status of PO-10233 and is it late?");
  log('E2E-23', silent === 'Answered' && dist === 1 && await badge() === 'Declined', `silent=${silent} dist-incidents=${dist} then ${(await t('decision-reason').textContent()).trim()}`);
  await page.request.post(`${base}/api/test/reset`);
  return out.join('\n');
}
