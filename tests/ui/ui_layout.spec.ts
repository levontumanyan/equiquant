import { test, expect } from '@playwright/test';

test('metric row elements are within container', async ({ page }) => {
  await page.goto('http://localhost:5173/');
  // Navigate to Profile Builder tab
  await page.getByRole('button', { name: 'Profile Builder' }).click();
  
  const container = page.locator('.profile-builder');
  const row = page.locator('.weight-slider').first();
  const removeButton = row.locator('.remove-metric');
  
  const containerBox = await container.boundingBox();
  const removeButtonBox = await removeButton.boundingBox();
  
  if (containerBox && removeButtonBox) {
    expect(removeButtonBox.x + removeButtonBox.width).toBeLessThanOrEqual(containerBox.x + containerBox.width + 10);
  }
});
