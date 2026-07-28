import { chromium } from 'playwright';
const errs = [];
const b = await chromium.launch();
const p = await b.newPage();
p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
await p.goto('http://localhost:5173/login');
await p.evaluate(() => localStorage.setItem('language','en'));
await p.reload();
await p.fill('#username','admin'); await p.fill('#password','admin12345');
await p.click('button[type="submit"]');
await p.waitForURL('http://localhost:5173/');
await p.goto('http://localhost:5173/activities');
await p.waitForTimeout(2500);

const check = async (label, sel) => console.log(`${await p.locator(sel).count() > 0 ? 'OK  ':'FAIL'} ${label}`);
await check('rows present', 'tbody tr');
await check('action badge', 'text=/Created|Signed in|Generated/');
await check('actor filter', '#ac-actor');
await check('entity filter', '#ac-entity');
const rows = await p.locator('tbody tr').count();
console.log('row count:', rows);

// detail dialog with before/after
await p.locator('tbody tr').first().click();
await p.waitForTimeout(700);
await check('dialog open', '[role="dialog"], .fixed');
await check('changes table', 'text=/Changes/');
await p.screenshot({ path: 'act_en.png', fullPage: false });
await p.keyboard.press('Escape');

// filter narrows results
await p.selectOption('#ac-action', 'login');
await p.waitForTimeout(1500);
console.log('rows after action=login filter:', await p.locator('tbody tr').count());

console.log('console errors:', errs.length, errs.slice(0,3));
await b.close();
