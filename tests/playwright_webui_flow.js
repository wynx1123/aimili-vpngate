async page => {
  await page.locator('label.mode-option').filter({ hasText: '固定 IP 地址' }).click();
  const visible = await page.locator('#fixed-ip-field').isVisible();
  await page.locator('#routing-fixed-ip').selectOption('jp-03');
  await page.getByRole('button', { name: '保存路由策略' }).click();
  await page.waitForFunction(() => document.querySelector('#summary-routing')?.textContent.includes('固定 IP') && document.querySelector('#fact-ip')?.textContent.includes('126.88.14.201'), null, { timeout: 10000 });
  return { visible, route: await page.locator('#summary-routing').textContent(), ip: await page.locator('#fact-ip').textContent() };
}