const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Collect all image load events
  const imageResults = [];
  page.on('response', async (r) => {
    const url = r.url();
    if (url.includes('/api/nail/image')) {
      const ct = r.headers()['content-type'] || '';
      const cl = parseInt(r.headers()['content-length'] || '0');
      const status = r.status();
      const isJpeg = ct.includes('jpeg') || ct.includes('jpg');
      imageResults.push({ url: url.substring(0, 100), status, size: cl, isImage: isJpeg });
      console.log(`  IMG: HTTP ${status} ${cl} bytes ${ct}`);
    }
  });

  try {
    // Step 1: Go to the nail chat page
    console.log('1. Opening nail chat page...');
    await page.goto('http://localhost:3000/workspace/chats/new?mode=nail', {
      waitUntil: 'networkidle',
      timeout: 15000
    });
    await page.waitForTimeout(2000);

    // Check if logged in
    const url = page.url();
    console.log(`   URL: ${url}`);

    // If redirected to login, we need to log in first
    if (url.includes('/login') || url.includes('/sign-in')) {
      console.log('2. Login required. Looking for login form...');
      // Try to find login form
      const emailInput = await page.$('input[type="email"], input[name="email"]');
      if (emailInput) {
        console.log('   Found login form, logging in...');
        await emailInput.fill('dev@nailflow.dev');
        const pwInput = await page.$('input[type="password"], input[name="password"]');
        if (pwInput) {
          await pwInput.fill('nail123456');
          const submitBtn = await page.$('button[type="submit"]');
          if (submitBtn) await submitBtn.click();
          await page.waitForTimeout(3000);
          console.log(`   After login URL: ${page.url()}`);
        }
      }
    }

    // Step 3: Check if we see the chat input
    console.log('3. Checking page content...');
    const chatInput = await page.$('textarea[name="message"]');
    if (chatInput) {
      console.log('   Chat input found');

      // Type and send a message
      console.log('4. Sending try-on message...');
      await chatInput.fill('请调用 unified_tryon_tool 进行一键 AI 美甲试戴。\nhand_image_path: "data/uploads/hands/ca3f9c2ccf3c.jpg"\nnail_style_image_path: "data/styles/001.jpg"');
      await page.waitForTimeout(500);

      // Find send button and click
      const sendBtn = await page.$('button[type="submit"], [aria-label="Send"]');
      if (sendBtn) {
        await sendBtn.click();
        console.log('   Message sent, waiting for response...');

        // Wait for response (up to 90 seconds)
        await page.waitForTimeout(5000);

        // Wait for image to appear or request to complete
        try {
          await page.waitForFunction(() => {
            const imgs = document.querySelectorAll('img');
            return Array.from(imgs).some(img => img.src.includes('/api/nail/image'));
          }, { timeout: 90000 });
          console.log('   Image element found in DOM!');
        } catch {
          console.log('   No image element appeared (timeout)');
        }

        await page.waitForTimeout(2000);

        // Take screenshot
        await page.screenshot({ path: '/tmp/nail_tryon_result.png', fullPage: true });
        console.log('5. Screenshot saved to /tmp/nail_tryon_result.png');

        // Check for image elements
        const imgs = await page.$$('img');
        const nailImgs = [];
        for (const img of imgs) {
          const src = await img.getAttribute('src');
          if (src && src.includes('/api/nail/image')) {
            nailImgs.push(src);
          }
        }
        console.log(`   Nail images found: ${nailImgs.length}`);
        for (const src of nailImgs) {
          console.log(`     ${src}`);
        }
      } else {
        console.log('   Send button not found');
      }
    } else {
      console.log('   Chat input not found');
      console.log('   Page title:', await page.title());
      const body = await page.$('body');
      if (body) {
        const text = await body.innerText();
        console.log('   Body text (first 500):', text.substring(0, 500));
      }
      await page.screenshot({ path: '/tmp/nail_page.png', fullPage: true });
      console.log('   Screenshot saved to /tmp/nail_page.png');
    }

  } catch (e) {
    console.error('Error:', e.message);
    await page.screenshot({ path: '/tmp/nail_error.png', fullPage: true });
  }

  // Summary
  console.log('\n=== Image Load Results ===');
  if (imageResults.length === 0) {
    console.log('No image requests detected');
  } else {
    const ok = imageResults.filter(r => r.isImage);
    const bad = imageResults.filter(r => !r.isImage || r.status >= 400);
    console.log(`Total: ${imageResults.length}, OK: ${ok.length}, Failed: ${bad.length}`);
    for (const r of imageResults) {
      console.log(`  ${r.status} ${r.size} ${r.isImage ? '✅' : '❌'} ${r.url}`);
    }
  }

  await browser.close();
})();
