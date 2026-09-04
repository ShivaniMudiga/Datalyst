/** The chart inference is the one place a wrong guess silently misleads.
 *  Run: node --experimental-strip-types src/lib/chart.test.ts   (no deps) */
import assert from 'node:assert/strict'
import { buildChart, needsSmallMultiples, niceTicks, unitOf, labelOf, formatValue } from './chart.ts'

// Numbers arrive as strings from the API; dates must not be read as numbers.
const monthly = [
  { month: '2026-06-01', orders: '3419', gross_gmv: '11920000.50' },
  { month: '2026-07-01', orders: '5639', gross_gmv: '15400000.00' },
  { month: '2026-08-01', orders: '3925', gross_gmv: '13580000.25' },
]
const timeChart = buildChart(monthly)
if (!timeChart || timeChart.form !== 'line') throw new Error('expected a line chart')
assert.equal(timeChart.labelKey, 'month')
assert.deepEqual(timeChart.series, ['orders', 'gross_gmv'])

// Out-of-order rows are sorted by time, not left as the query returned them.
const shuffled = buildChart([monthly[2], monthly[0], monthly[1]])
if (!shuffled || shuffled.form !== 'line') throw new Error('expected a line chart')
assert.deepEqual(shuffled.points.map((point) => point.label), ['2026-06-01', '2026-07-01', '2026-08-01'])

// A category plus measures is a bar chart, ranked by the first measure.
const bars = buildChart([
  { category: 'Footwear', units: '13645' },
  { category: 'Accessories', units: '16794' },
])
if (!bars || bars.form !== 'bar') throw new Error('expected a bar chart')
assert.deepEqual(bars.points.map((point) => point.label), ['Accessories', 'Footwear'])

// One row of numbers is a headline, not a plot. Ids are never measures.
assert.equal(buildChart([{ total_orders: '77486' }])?.form, 'stats')
assert.equal(buildChart([{ seller_id: '4', seller_name: 'Vastra' }, { seller_id: '9', seller_name: 'Fabrica' }]), null)

// Units are read from the column name; a count that contains "total" is not money.
assert.equal(unitOf('total_orders'), 'count')
assert.equal(unitOf('gross_gmv'), 'currency')
assert.equal(unitOf('return_pct'), 'percent')
assert.equal(formatValue('gross_gmv', 24020000), '₹2.4 Cr')
assert.equal(formatValue('return_pct', 20.53), '20.5%')
assert.equal(formatValue('total_orders', 73400), '73.4 K')
assert.equal(labelOf('gmv_return_loss_pct'), 'GMV Return Loss Pct')

// Incomparable scales must never share one axis.
const points = [{ values: [3419, 11920000] }, { values: [5639, 15400000] }]
assert.equal(needsSmallMultiples(['orders', 'gross_gmv'], points), true)
assert.equal(needsSmallMultiples(['orders', 'shipped_orders'], [{ values: [3419, 3200] }, { values: [5639, 5100] }]), false)

// Ticks a human would have picked.
assert.deepEqual(niceTicks(0, 6079), [0, 2000, 4000, 6000, 8000])
assert.equal(niceTicks(0, 21.6).at(-1)! >= 21.6, true) // never clip the peak

console.log('chart inference: all assertions passed')
