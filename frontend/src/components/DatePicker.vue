<template>
  <div class="date-picker" ref="containerRef">
    <input
      type="text"
      class="date-input"
      :value="modelValue"
      :placeholder="placeholder"
      :aria-label="ariaLabel"
      readonly
      @click="toggleCalendar"
      @keydown.enter="toggleCalendar"
      @keydown.escape="showCalendar = false"
    />
    <button
      v-if="modelValue"
      class="clear-btn"
      type="button"
      aria-label="清除日期"
      @click.stop="$emit('update:modelValue', '')"
    >×</button>

    <Teleport to="body">
      <div v-if="showCalendar" class="calendar-popup" :style="popupStyle" @mousedown.prevent>
        <div class="calendar-header">
          <button type="button" class="nav-btn" @click="changeMonth(-1)" aria-label="上一月">‹</button>
          <span class="month-label">{{ currentYear }}年{{ currentMonth + 1 }}月</span>
          <button type="button" class="nav-btn" @click="changeMonth(1)" aria-label="下一月">›</button>
        </div>
        <div class="weekday-row">
          <span v-for="d in weekdays" :key="d" class="weekday-cell">{{ d }}</span>
        </div>
        <div class="days-grid">
          <span
            v-for="(day, idx) in calendarDays"
            :key="idx"
            class="day-cell"
            :class="{
              'other-month': !day.currentMonth,
              'today': day.isToday,
              'selected': day.isSelected,
            }"
            @click="selectDay(day)"
          >{{ day.day }}</span>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  ariaLabel?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const containerRef = ref<HTMLElement | null>(null)
const showCalendar = ref(false)
const popupStyle = ref<Record<string, string>>({})

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

// Parse modelValue or default to today
const today = new Date()
const currentYear = ref(today.getFullYear())
const currentMonth = ref(today.getMonth())

watch(() => props.modelValue, (val) => {
  if (val) {
    const parts = val.split('-')
    if (parts.length === 3) {
      currentYear.value = parseInt(parts[0])
      currentMonth.value = parseInt(parts[1]) - 1
    }
  }
}, { immediate: true })

interface CalendarDay {
  day: number
  month: number
  year: number
  currentMonth: boolean
  isToday: boolean
  isSelected: boolean
  dateStr: string
}

const calendarDays = computed<CalendarDay[]>(() => {
  const y = currentYear.value
  const m = currentMonth.value
  const firstDay = new Date(y, m, 1).getDay()
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const daysInPrevMonth = new Date(y, m, 0).getDate()

  const days: CalendarDay[] = []
  const todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate())

  // Previous month days
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i
    const pm = m === 0 ? 11 : m - 1
    const py = m === 0 ? y - 1 : y
    const ds = formatDate(py, pm, d)
    days.push({ day: d, month: pm, year: py, currentMonth: false, isToday: ds === todayStr, isSelected: ds === props.modelValue, dateStr: ds })
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = formatDate(y, m, d)
    days.push({ day: d, month: m, year: y, currentMonth: true, isToday: ds === todayStr, isSelected: ds === props.modelValue, dateStr: ds })
  }

  // Next month days to fill 6 rows
  const remaining = 42 - days.length
  for (let d = 1; d <= remaining; d++) {
    const nm = m === 11 ? 0 : m + 1
    const ny = m === 11 ? y + 1 : y
    const ds = formatDate(ny, nm, d)
    days.push({ day: d, month: nm, year: ny, currentMonth: false, isToday: ds === todayStr, isSelected: ds === props.modelValue, dateStr: ds })
  }

  return days
})

function formatDate(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function changeMonth(delta: number) {
  let m = currentMonth.value + delta
  let y = currentYear.value
  if (m < 0) { m = 11; y-- }
  if (m > 11) { m = 0; y++ }
  currentMonth.value = m
  currentYear.value = y
}

function selectDay(day: CalendarDay) {
  emit('update:modelValue', day.dateStr)
  showCalendar.value = false
}

function toggleCalendar() {
  showCalendar.value = !showCalendar.value
  if (showCalendar.value) {
    nextTick(() => positionPopup())
  }
}

function positionPopup() {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  popupStyle.value = {
    position: 'fixed',
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    zIndex: '9999',
  }
}

function onClickOutside(e: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    // Also check if click is inside the popup
    const popup = document.querySelector('.calendar-popup')
    if (popup && popup.contains(e.target as Node)) return
    showCalendar.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<style scoped>
.date-picker {
  position: relative;
  display: inline-block;
  width: 100%;
  max-width: 400px;
}

.date-input {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 6px 32px 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
  box-sizing: border-box;
  cursor: pointer;
}
.date-input:focus { border-color: #58a6ff; outline: none; }

.clear-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #8b949e;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.clear-btn:hover { color: #e6edf3; }

.calendar-popup {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px;
  width: 280px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.calendar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.nav-btn {
  background: none;
  border: 1px solid #30363d;
  color: #e6edf3;
  border-radius: 4px;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-btn:hover { background: #21262d; }

.month-label {
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
}

.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  margin-bottom: 4px;
}
.weekday-cell {
  font-size: 12px;
  color: #8b949e;
  padding: 4px 0;
}

.days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
}

.day-cell {
  padding: 6px 0;
  font-size: 13px;
  color: #e6edf3;
  border-radius: 4px;
  cursor: pointer;
  line-height: 1.4;
}
.day-cell:hover { background: #21262d; }
.day-cell.other-month { color: #484f58; }
.day-cell.today { border: 1px solid #58a6ff; }
.day-cell.selected { background: #1f6feb; color: #fff; }
</style>
