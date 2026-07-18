async page => {
  await page.getByRole('button', { name: '管理设置' }).click();
  await page.getByRole('tab', { name: '节点来源' }).click();
  const providers = await page.locator('#source-name option').allTextContents();
  await page.locator('#source-catalog').selectOption('publicvpnlist');
  await page.locator('#source-name').selectOption('curated');
  await page.locator('#source-country').fill('japan');
  await page.getByRole('button', { name: '应用来源筛选' }).click();
  await page.getByRole('button', { name: '管理设置' }).click();
  await page.getByRole('tab', { name: '代理网络' }).click();
  await page.locator('#proxy-port').fill('7930');
  await page.getByRole('button', { name: '保存代理设置' }).click();
  return { providers, toast: await page.locator('#toast-region').innerText() };
}