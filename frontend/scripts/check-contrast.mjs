// Verifies WCAG contrast for every text/background pairing the UI actually renders.
// Tokens are parsed from globals.css (:root) so this check can never drift from the shipped values.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const cssPath = fileURLToPath(new URL("../src/app/globals.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");

function parseTokens(block) {
  const found = {};
  for (const [, name, l, c, h, a] of block.matchAll(
    /--([\w-]+):\s*oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*(?:\/\s*([\d.]+%?))?\s*\)/g,
  )) {
    const alpha = a === undefined ? 1 : a.endsWith("%") ? parseFloat(a) / 100 : parseFloat(a);
    found[name] = { l: +l, c: +c, h: +h, alpha };
  }
  return found;
}

// Light tokens are the first top-level :root block; dark tokens override them inside the
// prefers-color-scheme media query, so the dark set is "light, then dark overrides".
const lightTokens = parseTokens(css.match(/^:root\s*{([\s\S]*?)^}/m)?.[1] ?? "");
const darkOverrides = parseTokens(
  css.match(/@media \(prefers-color-scheme: dark\)\s*{\s*:root\s*{([\s\S]*?)}/)?.[1] ?? "",
);
const appearances = {
  light: lightTokens,
  dark: { ...lightTokens, ...darkOverrides },
};
let tokens = lightTokens;

function oklchToLinearSrgb({ l, c, h }) {
  const hr = (h * Math.PI) / 180;
  const a = c * Math.cos(hr);
  const b = c * Math.sin(hr);
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ].map((v) => Math.min(1, Math.max(0, v)));
}

const toGamma = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
const toLinear = (v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);

// Alpha tokens are composited in gamma space, which is how browsers blend by default.
function resolve(name, over) {
  const token = tokens[name];
  if (!token) throw new Error(`Token --${name} not found in :root`);
  const rgb = oklchToLinearSrgb(token).map(toGamma);
  if (token.alpha >= 1) return rgb;
  const base = resolve(over ?? "background");
  return rgb.map((v, i) => v * token.alpha + base[i] * (1 - token.alpha));
}

const luminance = (rgb) => {
  const [r, g, b] = rgb.map(toLinear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

function ratio(fg, bg) {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}

const TEXT = 4.5;
const NON_TEXT = 3;

// [foreground, background, minimum, where it is used]
const pairs = [
  ["foreground", "background", TEXT, "body text on page"],
  ["foreground", "card", TEXT, "body text on panels"],
  ["muted-foreground", "background", TEXT, "metadata on page"],
  ["muted-foreground", "card", TEXT, "metadata on panels"],
  ["muted-foreground", "muted", TEXT, "metadata on muted surfaces"],
  ["muted-foreground", "overdue-tint", TEXT, "row metadata on overdue rows"],
  ["muted-foreground", "selected", TEXT, "row metadata on the selected row"],
  ["foreground", "overdue-tint", TEXT, "row title on overdue rows"],
  ["foreground", "selected", TEXT, "row title on the selected row"],
  ["primary-foreground", "primary", TEXT, "primary button label"],
  ["primary", "card", TEXT, "links and today label on panels"],
  ["primary", "background", TEXT, "today label on page"],
  ["overdue", "background", TEXT, "overdue text on page"],
  ["overdue", "card", TEXT, "overdue text on panels"],
  ["overdue", "overdue-tint", TEXT, "overdue badge on overdue rows"],
  ["hot-foreground", "hot-tint", TEXT, "Hot badge"],
  ["warm-foreground", "warm-tint", TEXT, "Warm badge"],
  ["cold-foreground", "cold-tint", TEXT, "Cold badge"],
  ["success", "card", TEXT, "saved/sent confirmation"],
  ["destructive", "card", TEXT, "form error text"],
  ["ring", "background", NON_TEXT, "focus ring on page"],
  ["ring", "card", NON_TEXT, "focus ring on panels"],
  ["input-border", "card", NON_TEXT, "form control boundary"],
  ["foreground", "draft", TEXT, "draft text in the unsent bubble"],
  ["muted-foreground", "draft", TEXT, "draft label in the unsent bubble"],
  ["draft-border", "card", NON_TEXT, "unsent bubble outline on panels"],
  ["draft-border", "background", NON_TEXT, "unsent bubble outline on page"],
  ["foreground", "popover", TEXT, "menus and dialogs"],
];

let failures = 0;
for (const [appearance, set] of Object.entries(appearances)) {
  tokens = set;
  console.log(`\n${appearance.toUpperCase()}`);
  for (const [fg, bg, min, use] of pairs) {
    const value = ratio(resolve(fg, bg), resolve(bg));
    const ok = value >= min;
    if (!ok) failures += 1;
    console.log(
      `${ok ? "PASS" : "FAIL"}  ${value.toFixed(2).padStart(5)}:1 (min ${min})  --${fg} on --${bg}  [${use}]`,
    );
  }
}

if (failures > 0) {
  console.error(`\n${failures} contrast pair(s) below WCAG AA.`);
  process.exit(1);
}
console.log("\nAll contrast pairs meet WCAG AA in light and dark.");
