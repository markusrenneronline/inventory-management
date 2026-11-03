<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click="close" @keyup.esc="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <p v-if="backlogItem" class="item-summary">
              {{ t('purchaseOrder.item') }}: {{ backlogItem.item_name }} ({{ backlogItem.item_sku }})
            </p>

            <div v-if="loading" class="state-message">{{ t('common.loading') }}</div>
            <div v-else-if="error" class="error-message">{{ error }}</div>

            <!-- View mode: read-only PO -->
            <dl v-if="mode === 'view' && purchaseOrder && !loading" class="po-details">
              <dt>{{ t('purchaseOrder.poId') }}</dt><dd>{{ purchaseOrder.id }}</dd>
              <dt>{{ t('purchaseOrder.supplier') }}</dt><dd>{{ purchaseOrder.supplier_name }}</dd>
              <dt>{{ t('purchaseOrder.quantity') }}</dt><dd>{{ purchaseOrder.quantity }}</dd>
              <dt>{{ t('purchaseOrder.unitCost') }}</dt><dd>{{ formatMoney(purchaseOrder.unit_cost) }}</dd>
              <dt>{{ t('purchaseOrder.totalValue') }}</dt><dd>{{ formatMoney(purchaseOrder.quantity * purchaseOrder.unit_cost) }}</dd>
              <dt>{{ t('purchaseOrder.expectedDelivery') }}</dt><dd>{{ formatDate(purchaseOrder.expected_delivery_date) }}</dd>
              <dt>{{ t('purchaseOrder.status') }}</dt><dd>{{ purchaseOrder.status }}</dd>
              <dt>{{ t('purchaseOrder.createdDate') }}</dt><dd>{{ formatDate(purchaseOrder.created_date) }}</dd>
              <template v-if="purchaseOrder.notes">
                <dt>{{ t('purchaseOrder.notes') }}</dt><dd>{{ purchaseOrder.notes }}</dd>
              </template>
            </dl>

            <!-- Create mode -->
            <form v-else-if="mode === 'create'" id="po-form" class="po-form" @submit.prevent="submit">
              <div class="form-group">
                <label for="po-supplier">{{ t('purchaseOrder.supplier') }}</label>
                <input id="po-supplier" v-model="form.supplier_name" type="text" required
                       :placeholder="t('purchaseOrder.supplierPlaceholder')" class="po-input" />
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                  <input id="po-quantity" v-model.number="form.quantity" type="number" min="1" step="1" required class="po-input" />
                </div>
                <div class="form-group">
                  <label for="po-unit-cost">{{ t('purchaseOrder.unitCost') }}</label>
                  <input id="po-unit-cost" v-model.number="form.unit_cost" type="number" min="0" step="0.01" required class="po-input" />
                </div>
              </div>
              <div class="form-group">
                <label for="po-delivery">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input id="po-delivery" v-model="form.expected_delivery_date" type="date" required class="po-input" />
              </div>
              <div class="form-group">
                <label for="po-notes">{{ t('purchaseOrder.notes') }}</label>
                <textarea id="po-notes" v-model="form.notes" rows="3" class="po-input"></textarea>
              </div>
            </form>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" type="button" @click="close">{{ t('common.close') }}</button>
            <button v-if="mode === 'create'" class="btn-primary" type="submit" form="po-form" :disabled="!canSubmit">
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '../composables/useI18n'
import { api } from '../api'
import { formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'PurchaseOrderModal',
  props: {
    isOpen: { type: Boolean, required: true },
    backlogItem: { type: Object, default: null },
    mode: { type: String, default: 'create', validator: (v) => ['create', 'view'].includes(v) }
  },
  emits: ['close', 'po-created'],
  setup(props, { emit }) {
    const { t, currentCurrency, currentLocale } = useI18n()

    const emptyForm = () => ({
      supplier_name: '',
      quantity: 1,
      unit_cost: 0,
      expected_delivery_date: '',
      notes: ''
    })
    const form = ref(emptyForm())
    const purchaseOrder = ref(null)
    const loading = ref(false)
    const submitting = ref(false)
    const error = ref(null)

    const canSubmit = computed(() =>
      !submitting.value &&
      form.value.supplier_name.trim() !== '' &&
      Number.isInteger(form.value.quantity) && form.value.quantity >= 1 &&
      typeof form.value.unit_cost === 'number' && form.value.unit_cost >= 0 &&
      form.value.expected_delivery_date !== ''
    )

    const errorMessage = (err, fallbackKey) =>
      err.response?.data?.detail || t(fallbackKey)

    const loadPurchaseOrder = async () => {
      loading.value = true
      try {
        purchaseOrder.value = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
      } catch (err) {
        error.value = errorMessage(err, 'purchaseOrder.loadFailed')
        console.error('Failed to load purchase order:', err)
      } finally {
        loading.value = false
      }
    }

    // Reset on every open so stale data/errors from a previous item never show.
    watch(
      () => [props.isOpen, props.backlogItem, props.mode],
      () => {
        if (!props.isOpen || !props.backlogItem) return
        error.value = null
        purchaseOrder.value = null
        const item = props.backlogItem
        form.value = emptyForm()
        // Shortfall is what actually has to be ordered; at least 1 to satisfy server validation.
        form.value.quantity = Math.max(1, (item.quantity_needed || 0) - (item.quantity_available || 0))
        if (props.mode === 'view') loadPurchaseOrder()
      },
      { immediate: true }
    )

    const submit = async () => {
      if (!canSubmit.value) return
      submitting.value = true
      error.value = null
      try {
        const created = await api.createPurchaseOrder({
          backlog_item_id: props.backlogItem.id,
          supplier_name: form.value.supplier_name.trim(),
          quantity: form.value.quantity,
          unit_cost: form.value.unit_cost,
          expected_delivery_date: form.value.expected_delivery_date,
          notes: form.value.notes.trim() || null
        })
        emit('po-created', created)
      } catch (err) {
        // Server returns 404/400/409 with a human-readable detail.
        error.value = errorMessage(err, 'purchaseOrder.createFailed')
        console.error('Failed to create purchase order:', err)
      } finally {
        submitting.value = false
      }
    }

    const close = () => emit('close')

    // @keyup.esc on the overlay only fires with focus inside; listen globally instead.
    const onKeydown = (e) => { if (e.key === 'Escape' && props.isOpen) close() }
    onMounted(() => window.addEventListener('keydown', onKeydown))
    onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

    const formatMoney = (usd) => {
      const n = Number(usd)
      return Number.isFinite(n) ? formatCurrencyWithDecimals(n, currentCurrency.value, 2) : ''
    }

    const formatDate = (value) => {
      if (!value) return ''
      const d = new Date(value)
      if (isNaN(d.getTime())) return value
      return d.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US')
    }

    return {
      t, form, purchaseOrder, loading, submitting, error, canSubmit,
      submit, close, formatMoney, formatDate
    }
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 90%;
  max-width: 560px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 2px solid #e2e8f0;
}

.modal-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  padding: 2rem;
  overflow-y: auto;
  flex: 1;
}

.item-summary {
  margin: 0 0 1.5rem;
  color: #64748b;
  font-size: 0.95rem;
}

.state-message {
  text-align: center;
  padding: 2rem;
  color: #64748b;
}

.error-message {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
}

.po-input {
  padding: 0.75rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.po-input:focus {
  outline: none;
  border-color: #667eea;
}

.po-details {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.75rem 1.5rem;
  margin: 0;
}

.po-details dt {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
}

.po-details dd {
  margin: 0;
  color: #0f172a;
}

.modal-footer {
  padding: 1.5rem 2rem;
  border-top: 2px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary {
  background: #f1f5f9;
  color: #475569;
}

.btn-secondary:hover {
  background: #e2e8f0;
}

.btn-primary {
  background: #0f172a;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
