import React, { useCallback, useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
  LayoutChangeEvent,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import Ionicons from "@react-native-vector-icons/ionicons";
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';
import { localDateString } from '../src/utils/date';
import { parseAmount } from '../src/utils/numbers';

interface WeightEntry {
  id: string;
  weight_kg: number;
  date: string;   // YYYY-MM-DD, the user's day
}

interface PersonalRecord {
  exercise_name: string;
  best_weight: number;          // kg; 0 for bodyweight exercises
  best_reps_at_weight: number;
  best_bodyweight_reps: number;
  date: string | null;
}

const KG_TO_LB = 2.20462;
const RANGES = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 365, label: '1 year' },
];

const dayNumber = (iso: string) => Math.floor(new Date(`${iso}T00:00:00`).getTime() / 86400000);

function shortDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

// Weight trend drawn with plain views: a dot per entry joined by lines.
function WeightChart({ entries, toUnit, unit }: { entries: WeightEntry[]; toUnit: (kg: number) => number; unit: string }) {
  const [width, setWidth] = useState(0);
  const height = 150;
  const pad = 8;
  const values = entries.map(e => toUnit(e.weight_kg));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 1);           // at least 1 unit tall
  const first = dayNumber(entries[0].date);
  const span = Math.max(dayNumber(entries[entries.length - 1].date) - first, 1);
  const points = entries.map((e, i) => ({
    x: pad + ((dayNumber(e.date) - first) / span) * (width - pad * 2),
    y: pad + ((max - values[i]) / spread) * (height - pad * 2),
  }));

  return (
    <View>
      <View style={styles.chartLabels}>
        <Text style={styles.chartAxis}>{Math.round(max * 10) / 10} {unit}</Text>
      </View>
      <View
        style={[styles.chart, { height }]}
        onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
        testID="weight-chart"
      >
        {width > 0 && points.slice(1).map((p, i) => {
          const a = points[i];
          const len = Math.hypot(p.x - a.x, p.y - a.y);
          const angle = Math.atan2(p.y - a.y, p.x - a.x);
          return (
            <View
              key={`l${i}`}
              style={[styles.chartLine, {
                width: len,
                left: (a.x + p.x) / 2 - len / 2,
                top: (a.y + p.y) / 2 - 1,
                transform: [{ rotate: `${angle}rad` }],
              }]}
            />
          );
        })}
        {width > 0 && points.map((p, i) => (
          <View key={`d${i}`} style={[styles.chartDot, { left: p.x - 4, top: p.y - 4 }]} />
        ))}
      </View>
      <View style={styles.chartLabels}>
        <Text style={styles.chartAxis}>{Math.round(min * 10) / 10} {unit}</Text>
        <Text style={styles.chartAxis}>{shortDate(entries[0].date)} – {shortDate(entries[entries.length - 1].date)}</Text>
      </View>
    </View>
  );
}

export default function Progress() {
  const router = useRouter();
  const { profile, loadProfile } = useUserStore();
  const unit: 'kg' | 'lbs' = (profile?.unit_preference as 'kg' | 'lbs') || 'kg';
  const toUnit = (kg: number) => (unit === 'lbs' ? kg * KG_TO_LB : kg);
  const show = (kg: number) => Math.round(toUnit(kg) * 10) / 10;

  const [entries, setEntries] = useState<WeightEntry[]>([]);
  const [records, setRecords] = useState<PersonalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [range, setRange] = useState(90);
  const [weightText, setWeightText] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!profile?.id) return;
    setError('');
    try {
      const [w, r] = await Promise.all([
        api.get(`/weight/logs/${profile.id}`, { params: { days: 365 } }),
        api.get(`/workout/personal-records/${profile.id}`),
      ]);
      setEntries(w.data || []);
      setRecords(r.data || []);
    } catch (e) {
      console.log('Error loading progress:', e);
      setError('Couldn’t load your progress. Pull down or reopen to try again.');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, [profile?.id]));

  const logWeight = async () => {
    const value = parseAmount(weightText);
    if (!value || !profile?.id) {
      Alert.alert('Enter your weight', `Type today's weight in ${unit}, e.g. ${unit === 'kg' ? '82.5' : '182'}.`);
      return;
    }
    const kg = unit === 'lbs' ? value / KG_TO_LB : value;
    setSaving(true);
    try {
      await api.post('/weight/log', {
        user_id: profile.id,
        weight_kg: Math.round(kg * 100) / 100,
        date: localDateString(),
      });
      setWeightText('');
      await load();
      loadProfile().catch(() => {});   // targets follow the 7-day average
    } catch (e: any) {
      Alert.alert('Couldn’t save', e?.response?.data?.detail?.message || 'Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const deleteEntry = (entry: WeightEntry) => {
    Alert.alert('Delete entry', `Remove ${show(entry.weight_kg)} ${unit} on ${shortDate(entry.date)}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/weight/log/${entry.id}`, { params: { user_id: profile?.id } });
            await load();
            loadProfile().catch(() => {});
          } catch {
            Alert.alert('Error', 'Failed to delete entry');
          }
        },
      },
    ]);
  };

  // Entries in the chosen range, and the summary numbers
  const today = dayNumber(localDateString());
  const inRange = useMemo(
    () => entries.filter(e => today - dayNumber(e.date) < range),
    [entries, range, today]
  );
  const latest = entries[entries.length - 1];
  const loggedToday = latest?.date === localDateString();
  const weekAvg = useMemo(() => {
    if (!latest) return null;
    const week = entries.filter(e => dayNumber(latest.date) - dayNumber(e.date) < 7);
    return week.reduce((a, e) => a + e.weight_kg, 0) / week.length;
  }, [entries, latest]);
  const change = inRange.length > 1 ? inRange[inRange.length - 1].weight_kg - inRange[0].weight_kg : null;

  const strengthRecords = records.filter(r => r.best_weight > 0);
  const bodyweightRecords = records.filter(r => r.best_weight <= 0 && r.best_bodyweight_reps > 0);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} testID="progress-back">
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Progress</Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ flex: 1 }} />
      ) : (
        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {!!error && <Text style={styles.error}>{error}</Text>}

          {/* ── Body weight ─────────────────────────────── */}
          <Text style={styles.sectionTitle}>Body weight</Text>
          <View style={styles.card}>
            <View style={styles.logRow}>
              <TextInput
                style={styles.weightInput}
                placeholder={loggedToday ? `Today: ${show(latest!.weight_kg)} ${unit}` : `Today's weight (${unit})`}
                placeholderTextColor={colors.textMuted}
                keyboardType="decimal-pad"
                value={weightText}
                onChangeText={setWeightText}
                returnKeyType="done"
                onSubmitEditing={logWeight}
                testID="weight-input"
              />
              <TouchableOpacity style={styles.logBtn} onPress={logWeight} disabled={saving} testID="weight-log-btn">
                {saving
                  ? <ActivityIndicator size="small" color={colors.textOnPrimary} />
                  : <Text style={styles.logBtnText}>{loggedToday ? 'Update' : 'Log'}</Text>}
              </TouchableOpacity>
            </View>
            <Text style={styles.hint}>
              Weigh yourself at the same time each day, ideally in the morning. Your targets follow your
              7-day average, so day-to-day swings don't change them.
            </Text>

            {latest && (
              <View style={styles.statsRow}>
                <View style={styles.stat}>
                  <Text style={styles.statValue}>{show(latest.weight_kg)}</Text>
                  <Text style={styles.statLabel}>latest ({unit})</Text>
                </View>
                <View style={styles.stat}>
                  <Text style={styles.statValue}>{weekAvg != null ? show(weekAvg) : '–'}</Text>
                  <Text style={styles.statLabel}>7-day average</Text>
                </View>
                <View style={styles.stat}>
                  <Text style={[styles.statValue, change != null && change < 0 && { color: colors.success }]}>
                    {change == null ? '–' : `${change > 0 ? '+' : ''}${show(change)}`}
                  </Text>
                  <Text style={styles.statLabel}>change, {RANGES.find(r => r.days === range)?.label}</Text>
                </View>
              </View>
            )}

            <View style={styles.rangeRow}>
              {RANGES.map(r => (
                <TouchableOpacity
                  key={r.days}
                  style={[styles.rangeChip, range === r.days && styles.rangeChipActive]}
                  onPress={() => setRange(r.days)}
                >
                  <Text style={[styles.rangeChipText, range === r.days && styles.rangeChipTextActive]}>{r.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {inRange.length >= 2 ? (
              <WeightChart entries={inRange} toUnit={toUnit} unit={unit} />
            ) : (
              <Text style={styles.empty}>
                {entries.length === 0
                  ? 'Log your weight to start your trend.'
                  : 'Log at least two days in this range to see your trend.'}
              </Text>
            )}

            {entries.length > 0 && (
              <View style={styles.entryList}>
                {[...entries].reverse().slice(0, 7).map(e => (
                  <View key={e.id} style={styles.entryRow}>
                    <Text style={styles.entryDate}>{shortDate(e.date)}</Text>
                    <Text style={styles.entryValue}>{show(e.weight_kg)} {unit}</Text>
                    <TouchableOpacity onPress={() => deleteEntry(e)} hitSlop={8}>
                      <Ionicons name="trash-outline" size={16} color={colors.textMuted} />
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            )}
          </View>

          {/* ── Personal records ────────────────────────── */}
          <Text style={styles.sectionTitle}>Personal records</Text>
          <View style={styles.card}>
            {records.length === 0 ? (
              <Text style={styles.empty}>
                Finish a workout with your weights and reps logged, and your best lifts will appear here.
              </Text>
            ) : (
              <>
                {strengthRecords.map(r => (
                  <View key={r.exercise_name} style={styles.recordRow}>
                    <Text style={styles.recordName} numberOfLines={1}>{r.exercise_name}</Text>
                    <Text style={styles.recordValue}>{show(r.best_weight)} {unit} × {r.best_reps_at_weight}</Text>
                    <Text style={styles.recordDate}>{shortDate(r.date)}</Text>
                  </View>
                ))}
                {bodyweightRecords.map(r => (
                  <View key={r.exercise_name} style={styles.recordRow}>
                    <Text style={styles.recordName} numberOfLines={1}>{r.exercise_name}</Text>
                    <Text style={styles.recordValue}>{r.best_bodyweight_reps} reps</Text>
                    <Text style={styles.recordDate}>bodyweight</Text>
                  </View>
                ))}
              </>
            )}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
  backBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '600', color: colors.text },
  scrollContent: { padding: 20, paddingBottom: 40 },
  error: { color: colors.error, marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 10, marginTop: 8 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 20, gap: 12 },
  logRow: { flexDirection: 'row', gap: 10 },
  weightInput: {
    flex: 1, backgroundColor: colors.surfaceLight, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12,
    color: colors.text, fontSize: 16,
  },
  logBtn: {
    backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 20, justifyContent: 'center', minWidth: 84,
    alignItems: 'center',
  },
  logBtnText: { color: colors.textOnPrimary, fontWeight: '700', fontSize: 15 },
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  stat: { flex: 1, alignItems: 'center' },
  statValue: { color: colors.text, fontSize: 20, fontWeight: '700' },
  statLabel: { color: colors.textSecondary, fontSize: 11, marginTop: 2, textAlign: 'center' },
  rangeRow: { flexDirection: 'row', gap: 8 },
  rangeChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: colors.surfaceLight },
  rangeChipActive: { backgroundColor: colors.primary },
  rangeChipText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  rangeChipTextActive: { color: colors.textOnPrimary },
  chart: { backgroundColor: colors.backgroundSecondary, borderRadius: 10, overflow: 'hidden' },
  chartLine: { position: 'absolute', height: 2, backgroundColor: colors.primary, opacity: 0.6 },
  chartDot: { position: 'absolute', width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary },
  chartLabels: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 4 },
  chartAxis: { color: colors.textMuted, fontSize: 11 },
  empty: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },
  entryList: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 },
  entryRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 12 },
  entryDate: { color: colors.textSecondary, width: 70, fontSize: 14 },
  entryValue: { color: colors.text, flex: 1, fontSize: 14, fontWeight: '600' },
  recordRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 },
  recordName: { color: colors.text, flex: 1, fontSize: 14 },
  recordValue: { color: colors.primary, fontSize: 14, fontWeight: '700' },
  recordDate: { color: colors.textMuted, fontSize: 12, width: 70, textAlign: 'right' },
});
