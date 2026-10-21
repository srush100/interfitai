// Turns meal-plan ingredient lines into a shopping list.
//
// Meal plans list meat, fish, rice, pasta and grains at COOKED weight (that's
// what the nutrition numbers are for), so the shopping amount is converted back
// to what you buy: dry rice/pasta/grains and raw meat/fish. Beans are shown as
// cans, oils in tablespoons, and spices as pantry items.

export type Aisle =
  | 'Fruit & veg'
  | 'Meat & seafood'
  | 'Dairy & eggs'
  | 'Bakery'
  | 'Grains, rice & pasta'
  | 'Pantry';

export const AISLE_ORDER: Aisle[] = [
  'Fruit & veg', 'Meat & seafood', 'Dairy & eggs', 'Bakery', 'Grains, rice & pasta', 'Pantry',
];

export interface ParsedIngredient {
  key: string;         // merge key (same food, same kind of amount)
  name: string;        // display name
  grams?: number;      // gram-measured items
  units?: number;      // whole-unit items (eggs, slices…)
  unitName?: string;   // "large eggs", "slices sourdough bread"
  other?: string;      // anything else, shown as written
}

const DESCRIPTORS = /\b(grilled|baked|roasted|steamed|boiled|cooked|pan[- ]fried|fried|fresh|sliced|diced|chopped|shredded|minced|boneless|skinless|lean|plain|organic|large|medium|small)\b/gi;

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// "Grilled chicken breast (cooked)" → "chicken breast"
export function baseName(raw: string): string {
  return raw
    .replace(/\([^)]*\)/g, ' ')
    .replace(DESCRIPTORS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

// One ingredient line from a meal plan, e.g. "150g Chicken breast",
// "2 large eggs (116g)", "1 slice sourdough bread (30g)", "Salt to taste".
export function parseIngredient(line: string, servings = 1): ParsedIngredient | null {
  const ing = (line || '').trim();
  if (!ing) return null;
  const g = ing.match(/^(\d+(?:\.\d+)?)\s*g\s+(.+)$/i);
  if (g) {
    const name = baseName(g[2]);
    return { key: `g|${name}`, name: g[2].replace(/\s*\((cooked|raw|dry)\)\s*$/i, '').trim(),
             grams: parseFloat(g[1]) * servings };
  }
  const u = ing.match(/^(\d+)\s+(.+?)\s*\(\d+(?:\.\d+)?\s*g\)$/i);
  if (u) {
    const unitName = u[2].trim();
    const plural = /^slices?\s/i.test(unitName)
      ? unitName.replace(/^slice\s/i, 'slices ')
      : unitName.endsWith('s') ? unitName : `${unitName}s`;
    return { key: `u|${baseName(plural)}`, name: plural, units: parseInt(u[1], 10) * servings, unitName: plural };
  }
  return { key: `o|${ing.toLowerCase()}`, name: ing, other: ing };
}

// Add one parsed line into the running list (same key → amounts add up).
export function addTo(list: Map<string, ParsedIngredient>, item: ParsedIngredient) {
  const cur = list.get(item.key);
  if (!cur) { list.set(item.key, { ...item }); return; }
  if (item.grams != null) cur.grams = (cur.grams || 0) + item.grams;
  if (item.units != null) cur.units = (cur.units || 0) + item.units;
}

const has = (name: string, words: string) => new RegExp(`\\b(${words})\\b`, 'i').test(name);

const SPICES = 'salt|pepper|black pepper|cinnamon|paprika|cumin|turmeric|oregano|thyme|rosemary|chili flakes|chilli flakes|chili powder|curry powder|garlic powder|onion powder|dried herbs|italian seasoning|seasoning|nutmeg|vanilla extract|baking powder|baking soda|stock cube';

export function aisleOf(name: string): Aisle {
  const n = name.toLowerCase();
  // Specific names first, so "green beans", "egg noodles", "rice milk" and
  // "peanut butter" don't fall into the wrong aisle
  if (has(n, 'almond milk|oat milk|soy milk|rice milk|cashew milk')) return 'Dairy & eggs';
  if (has(n, 'green beans?|snow peas|sugar snap peas')) return 'Fruit & veg';
  if (has(n, 'broth|stock|sauce|oil|vinegar|honey|syrup|jam|peanut butter|almond butter|cashew butter|nut butter|protein powder|whey|powder|seasoning|spice|salt|black pepper|flakes|cinnamon|paprika|cumin|nuts?|almonds?|walnuts?|cashews?|pecans?|pistachios?|seeds?|chia|flaxseed|hummus|salsa|pesto|canned|tinned|beans?|chickpeas?|lentils?|tahini|coconut milk|coconut cream|chocolate|cocoa')) {
    return 'Pantry';
  }
  if (has(n, 'chicken|turkey|beef|steak|mince|pork|lamb|bacon|ham|sausage|kangaroo|duck|veal|salmon|tuna|cod|fish|prawns?|shrimp|barramundi|tilapia|mackerel|sardines?|trout|squid|calamari|mussels|scallops|crab|lobster|prosciutto|salami|chorizo')) {
    return 'Meat & seafood';
  }
  if (has(n, 'bread|toast|wraps?|tortillas?|pita|bagels?|muffins?|naans?|sourdough|crumpets?|croissants?|rolls?|buns?')) {
    return 'Bakery';
  }
  if (has(n, 'rice|pasta|spaghetti|penne|macaroni|noodles?|quinoa|oats|oatmeal|porridge|couscous|cereal|granola|muesli|flour|rice cakes?|gnocchi')) {
    return 'Grains, rice & pasta';
  }
  if (has(n, 'milk|yogurt|yoghurt|cheese|cheddar|cottage|feta|mozzarella|parmesan|halloumi|ricotta|butter|cream|eggs?|egg whites|skyr|kefir|tzatziki|ghee')) {
    return 'Dairy & eggs';
  }
  return 'Fruit & veg';
}

const fmtG = (g: number) => (g >= 1000 ? `${Math.round(g / 100) / 10}kg` : `${Math.round(g)}g`);

// What to buy, as one line: "Rice — 160g dry (≈450g cooked)"
export function shoppingLine(item: ParsedIngredient): string {
  const name = cap(item.name);
  if (item.units != null) return `${item.units} ${item.units === 1 ? item.unitName!.replace(/^slices\s/i, 'slice ').replace(/s$/, '') : item.unitName}`;
  if (item.grams == null) return name;
  const g = item.grams;
  const n = item.name.toLowerCase();
  const raw = has(n, 'raw|uncooked|dry');

  // Cooked weight in the plan → what you buy
  if (!raw && has(n, 'rice') && !has(n, 'rice cakes?|rice milk|rice noodles|cauliflower rice')) {
    return `${name} — ${fmtG(g / 2.8)} uncooked (≈${fmtG(g)} cooked)`;
  }
  if (!raw && has(n, 'pasta|spaghetti|penne|macaroni|fusilli|noodles?') && !has(n, 'zucchini')) {
    return `${name} — ${fmtG(g / 2.35)} dry (≈${fmtG(g)} cooked)`;
  }
  if (!raw && has(n, 'quinoa')) return `${name} — ${fmtG(g / 3)} uncooked (≈${fmtG(g)} cooked)`;
  if (!raw && has(n, 'couscous')) return `${name} — ${fmtG(g / 2.5)} dry (≈${fmtG(g)} cooked)`;
  if (has(n, 'lentils?|chickpeas?|beans?') && !has(n, 'green beans?|baked beans|coffee')) {
    const cans = Math.max(0.5, Math.ceil((g / 240) * 2) / 2);
    return `${name} — ${cans} × 400g can${cans > 1 ? 's' : ''} (≈${fmtG(g)} drained)`;
  }
  if (!raw && has(n, 'salmon|tuna steak|cod|fish|barramundi|tilapia|trout|prawns?|shrimp') && !has(n, 'smoked|canned|tinned|tuna in')) {
    return `${name} — ${fmtG(g * 1.2)} raw (≈${fmtG(g)} cooked)`;
  }
  if (!raw && has(n, 'chicken|turkey|beef|steak|mince|pork|lamb|kangaroo|duck|veal') &&
      !has(n, 'broth|stock|fat|ham|bacon|jerky|deli|sausage')) {
    return `${name} — ${fmtG(g * 1.33)} raw (≈${fmtG(g)} cooked)`;
  }
  // Oils by the spoon; spices are pantry items
  if (has(n, 'oil|ghee')) return `${name} — ${Math.max(1, Math.round(g / 13.6))} tbsp (${fmtG(g)})`;
  if (has(n, SPICES) && g <= 20) return `${name} (pantry)`;
  return `${name} — ${fmtG(g)}`;
}
