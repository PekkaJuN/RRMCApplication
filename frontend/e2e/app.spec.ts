import { expect, test } from "@playwright/test";

test("AC1, AC25: the app opens in Finnish with every service working", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Kuittisovellus");
  await expect(page.getByRole("heading", { level: 1, name: "Kuittisovellus" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Palveluiden tila" })).toHaveText(
    "Kaikki palvelut toiminnassa",
  );
});
