<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>
        <label class="budget-label" for="budget">{{ t('restocking.budgetLabel') }}</label>
        <div class="budget-row">
          <input id="budget" type="range" min="0" :max="maxBudget" :step="step" v-model.number="budget" class="slider" />
          <div class="budget-value">{{ formatMoney(budget) }}</div>
        </div>
      </div>

      <div class="restocking-grid">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ recommended.length }})</h3>
          </div>
          <div v-if="recommended.length === 0" class="loading">{{ t('restocking.empty') }}</div>
          <div v-else class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.itemName') }}</th>
                  <th>{{ t('restocking.table.quantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineCost') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recommended" :key="item.item_sku">
                  <td><strong>{{ item.item_sku }}</strong></td>
                  <td>{{ translateProductName(item.item_name) }}</td>
                  <td>{{ item.quantity }}</td>
                  <td>{{ formatMoney(item.unit_cost, 2) }}</td>
                  <td><strong>{{ formatMoney(item.lineCost, 2) }}</strong></td>
                  <td>{{ item.lead_time_days }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card summary-card">
          <div class="card-header">
            <h3 class="card-title">{{ t('restocking.summary') }}</h3>
          </div>
          <dl class="summary">
            <div class="summary-row">
              <dt>{{ t('restocking.totalSpent') }}</dt>
              <dd>{{ formatMoney(totalSpent, 2) }}</dd>
            </div>
            <div class="summary-row">
              <dt>{{ t('restocking.remainingBudget') }}</dt>
              <dd>{{ formatMoney(remaining, 2) }}</dd>
            </div>
            <div class="summary-row">
              <dt>{{ t('restocking.orderLeadTime') }}</dt>
              <dd>{{ t('restocking.days', { count: orderLeadTime }) }}</dd>
            </div>
          </dl>
          <button class="place-order" :disabled="recommended.length === 0 || submitting" @click="placeOrder">
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
          <div v-if="successMessage" class="message success-message">{{ successMessage }}</div>
          <div v-if="submitError" class="message error-message">{{ submitError }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()
    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const successMessage = ref('')
    const submitError = ref('')
    const step = 100

    // Budget logic is always in USD; only display is converted
    const formatMoney = (amount, decimals = 0) =>
      formatCurrencyWithDecimals(amount, currentCurrency.value, decimals)

    // Growth ratio, guarding against current_demand of 0
    const growth = (f) => f.current_demand > 0
      ? (f.forecasted_demand - f.current_demand) / f.current_demand
      : (f.forecasted_demand > 0 ? Infinity : 0)

    const candidates = computed(() =>
      forecasts.value
        .filter(f => f.trend !== 'decreasing')
        .sort((a, b) => growth(b) - growth(a))
    )

    // Slider max: cost of every candidate at forecasted quantity, rounded up to the step
    const maxBudget = computed(() => {
      const total = candidates.value.reduce((s, f) => s + f.forecasted_demand * f.unit_cost, 0)
      return Math.ceil(total / step) * step
    })

    // Greedy: take items in growth order, skip any that no longer fit the remaining budget
    const recommended = computed(() => {
      const picked = []
      let left = budget.value
      for (const f of candidates.value) {
        const lineCost = f.forecasted_demand * f.unit_cost
        if (f.forecasted_demand > 0 && lineCost <= left) {
          picked.push({ ...f, quantity: f.forecasted_demand, lineCost })
          left -= lineCost
        }
      }
      return picked
    })

    const totalSpent = computed(() => recommended.value.reduce((s, i) => s + i.lineCost, 0))
    const remaining = computed(() => budget.value - totalSpent.value)
    const orderLeadTime = computed(() =>
      recommended.value.reduce((m, i) => Math.max(m, i.lead_time_days), 0))

    const loadForecasts = async () => {
      try {
        forecasts.value = await api.getDemandForecasts()
        budget.value = Math.round(maxBudget.value / 2 / step) * step
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      submitting.value = true
      successMessage.value = ''
      submitError.value = ''
      try {
        const order = await api.createRestockingOrder(
          recommended.value.map(i => ({ sku: i.item_sku, quantity: i.quantity }))
        )
        successMessage.value = t('restocking.success', {
          orderNumber: order.order_number,
          days: order.lead_time_days
        })
      } catch (err) {
        submitError.value = t('restocking.error') + ': ' + (err.response?.data?.detail || err.message)
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t, loading, error, budget, maxBudget, step, recommended, totalSpent, remaining,
      orderLeadTime, submitting, successMessage, submitError, formatMoney,
      translateProductName, placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
}

.budget-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.budget-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.slider {
  flex: 1;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 140px;
  text-align: right;
}

.restocking-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 1000px) {
  .restocking-grid {
    grid-template-columns: 1fr;
  }
}

.summary {
  margin: 0 0 1.5rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 0.75rem 0;
  border-bottom: 1px solid #f1f5f9;
}

.summary-row dt {
  color: #64748b;
  font-size: 0.875rem;
}

.summary-row dd {
  margin: 0;
  font-weight: 700;
  color: #0f172a;
}

.place-order {
  width: 100%;
  padding: 0.75rem 1rem;
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.place-order:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.message {
  margin-top: 1rem;
  padding: 0.75rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.success-message {
  background: #d1fae5;
  color: #065f46;
}

.error-message {
  background: #fee2e2;
  color: #991b1b;
}
</style>
