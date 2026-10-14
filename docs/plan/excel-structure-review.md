# Review of the Event Order Excel (sample: event LR024-068)

File checked: `Event Order New.xlsx` (one event: Wedding-Day lunch, 14 Aug 2024, 225 pax, rate LKR 3,900, Banquet Hall).

## 1. What the file contains

| Sheet | What it is | Useful for |
|---|---|---|
| **Party Menu** | The menu for the event, grouped by section (Welcome drinks, Bites, Salads, Soup, Hot chaffer rice/noodles, Chicken, Pork, Shellfish, Vegetable, Action, Condiments, Desserts, Special drinks). Some dishes have cooked quantities that come from formulas. | Event features: type, meal, pax, rate, number of dishes per section. Chef's planned (prepared) quantity per dish. |
| **StockBalance** | Raw-material demand for the event (rice 29.25 kg, chicken thigh 51 kg, eggs 387, and so on). Columns: Demand, Jayalath, Market, Stores, Return, Rate, Amount. | The chef's demand in raw-material form. Return column is empty in this sample. |
| **Recepies** | Recipe book: the raw ingredients for each dish. | Converting a dish or category forecast into a raw-material order. |

## 2. The most important finding: the chef's demand is already a fixed rule

The quantities are **formulas based on pax**, for example:
- Chicken fried & devilled = pax ÷ 6.81 → about **147 g per guest**
- Pork devilled = pax ÷ 15 → about 67 g per guest
- Grilled sausages = pax ÷ 17 → about 59 g per guest
- French fries = pax ÷ 15 → about 67 g per guest
- Raw materials = recipe quantity per 100 pax × pax

**This is very good for the research.** It is the hotel's **real, documented chef's rule**, so you don't have to invent a baseline. Your research question becomes very clear:

> *The current system prepares a fixed amount per guest, whatever the event type, package, or day. Can a data-driven, risk-aware model do better?*

## 3. What is missing (the critical gap)

The file records **what the chef planned to prepare**. It does **not** record **what was actually eaten or left over**. Without that, there is no target for the model to learn.

For each event, the analysis needs these extra fields (one row per event, in a new small sheet):

| Field | Why |
|---|---|
| Event No | Links to the event order |
| **Actual guests attended** | Pax booked ≠ pax attended. Per-guest consumption needs actual guests. |
| **Leftover kg per category** (5 numbers) | Consumed = prepared − leftover. **This is the target variable.** |
| Ran short? (yes/no per category) | Marks events where consumption is capped |
| Data quality flag R / M / E | R = weighed, M = partly weighed, E = estimated by chef |

Prepared kg per category can be calculated from the Party Menu (dish quantity × section → category), so it does not need to be re-entered if the chef made the planned amount. If the kitchen changed the amount on the day, record the actual figure.

## 4. Questions for you

1. **For the 30 events, do you have leftover records?** (a waste log, kitchen notes, or the chef's memory)
   - If yes: great, we enter them in the new sheet.
   - If no: the chef and banquet manager estimate leftovers per category for each event (flag **E**), and you **weigh leftovers at every event from now until 14 Oct** (flag **R**). Estimated data is weaker, but it is acceptable if it is labelled and checked with the R-only robustness test.
2. **What are the numbers 340, 12 and 352 next to "Rate" (cells T10, U10, V10)?** They may be actual attendance (for example adults + children), which would be very useful.
3. **Is the "Return" column filled in after the event** (raw materials sent back to stores)? If yes, it shows over-ordering of raw materials, which is a useful extra measure.
4. **Is each event saved as a separate file like this one?** If yes, I will write a script that reads all 30 files automatically and builds the dataset, so you don't have to retype the menu data.

## 5. How the menu sections map to the 5 food categories (default)

| Category | Party Menu sections |
|---|---|
| Rice / starch | Hot chaffer rice, fried rice, noodles, pasta |
| Mains (protein) | Chicken, Pork, Fish, Shellfish, meat bites |
| Veg / sides | Vegetable, Salads, veg bites, Action counter |
| Desserts | Desserts |
| Beverages | Welcome drink, Special drinks |

Soup and condiments are left out by default, because they are small and hard to weigh. Tell me if your chef sees it differently.

## 6. Extra features this file gives us for free

- Event type (Wedding-Day, etc.), meal (Lunch/Dinner), location, date → weekday/weekend, month
- Package **rate per pax** (LKR 3,900): a strong signal of menu richness
- **Number of dishes per category**: more dishes usually means less of each dish is eaten
- "Unlimited" vs "Package" items

## 7. Bonus system feature for the thesis

Because the recipe sheet links dishes to raw ingredients, the app can go one step further: **forecast per category → safe quantity → automatic raw-material order** using your own recipes. That ties the forecast to purchasing, which is where the money is saved. It makes a strong "system design" chapter and is cheap to build, since the recipe data already exists.
