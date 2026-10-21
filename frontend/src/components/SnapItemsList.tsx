import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import Ionicons from '@react-native-vector-icons/ionicons';
import { colors } from '../theme/colors';
import api from '../services/api';

export interface SnapItem {
  name: string;
  key: string | null;
  grams: number;
  display: string;
  calories: number;
  protein: number;
  carbs: number;
  fats: number;
  per_100g?: Record<string, number> | null;
}

interface Props {
  items: SnapItem[];
  onChange: (items: SnapItem[]) => void;
}

// Plated-meal items: one compact line each ("4 large eggs · 232g").
// Tap a line to change its amount ("150g", "3 eggs"; 0 removes it), or add a
// missing item by name. Every number comes from the backend food database.
export default function SnapItemsList({ items, onChange }: Props) {
  const [editing, setEditing] = useState<number | null>(null); // index, or -1 = adding
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const close = () => {
    setEditing(null);
    setText('');
    setError('');
  };

  const remove = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx));
    close();
  };

  const submit = async () => {
    const t = text.trim();
    if (editing === null) return;
    if (editing >= 0 && (t === '' || /^0+(\.0+)?\s*g?$/i.test(t))) {
      remove(editing);
      return;
    }
    if (!t) {
      close();
      return;
    }
    const base = editing >= 0 ? items[editing] : null;
    setBusy(true);
    try {
      const res = await api.post('/food/item', {
        text: t,
        key: base?.key ?? undefined,
        name: base?.name ?? undefined,
        per_100g: base && !base.key ? base.per_100g : undefined,
      });
      const next = [...items];
      if (base) next[editing] = res.data;
      else next.push(res.data);
      onChange(next);
      close();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError((detail && typeof detail === 'object' && detail.message) || 'Couldn\u2019t work that out \u2014 try grams, e.g. 150g.');
    } finally {
      setBusy(false);
    }
  };

  const renderInput = (placeholder: string, onRemove?: () => void) => (
    <View style={styles.editRow}>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={(v) => { setText(v); setError(''); }}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        autoFocus
        returnKeyType="done"
        onSubmitEditing={submit}
        testID="snap-item-input"
      />
      {busy ? (
        <ActivityIndicator size="small" color={colors.primary} />
      ) : (
        <>
          <TouchableOpacity onPress={submit} hitSlop={8} testID="snap-item-save">
            <Ionicons name="checkmark" size={20} color={colors.primary} />
          </TouchableOpacity>
          {onRemove && (
            <TouchableOpacity onPress={onRemove} hitSlop={8} testID="snap-item-remove">
              <Ionicons name="trash-outline" size={18} color={colors.error} />
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={close} hitSlop={8}>
            <Ionicons name="close" size={20} color={colors.textMuted} />
          </TouchableOpacity>
        </>
      )}
    </View>
  );

  return (
    <View style={styles.list} testID="snap-items-list">
      {items.map((it, idx) =>
        editing === idx ? (
          <View key={`${it.name}-${idx}`}>{renderInput('e.g. 150g or 3 eggs', () => remove(idx))}</View>
        ) : (
          <TouchableOpacity
            key={`${it.name}-${idx}`}
            style={styles.row}
            onPress={() => { setEditing(idx); setText(`${it.grams}g`); setError(''); }}
            testID={`snap-item-${idx}`}
          >
            <Text style={styles.rowText} numberOfLines={1}>{it.display} · {it.grams}g</Text>
            <Text style={styles.rowCal}>{it.calories} cal</Text>
          </TouchableOpacity>
        ),
      )}
      {editing === -1 ? (
        renderInput('e.g. 30g cheddar or 1 tbsp olive oil')
      ) : (
        <TouchableOpacity
          onPress={() => { setEditing(-1); setText(''); setError(''); }}
          style={styles.addLink}
          testID="snap-add-item"
        >
          <Text style={styles.addText}>+ Add item</Text>
        </TouchableOpacity>
      )}
      {!!error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { marginTop: 10 },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 32, paddingVertical: 4 },
  rowText: { flex: 1, fontSize: 14, color: colors.textSecondary },
  rowCal: { fontSize: 13, color: colors.textMuted, marginLeft: 8 },
  editRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 40 },
  input: {
    flex: 1,
    fontSize: 14,
    color: colors.text,
    borderBottomWidth: 1,
    borderBottomColor: colors.primary,
    paddingVertical: 6,
  },
  addLink: { paddingVertical: 8, alignSelf: 'flex-start' },
  addText: { fontSize: 14, color: colors.primary, fontWeight: '600' },
  error: { fontSize: 12, color: colors.error, marginTop: 2 },
});
