import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

export default function MacroTargetsScreen() {
  const router = useRouter();
  const { profile, setProfile } = useUserStore();
  const [calorieAdjustment, setCalorieAdjustment] = useState(profile?.calorie_adjustment || 0);
  const [saving, setSaving] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  const macros = profile?.calculated_macros;

  const adjustedCalories = (macros?.calories || 0) + calorieAdjustment;
  const adjustedCarbs = Math.round((macros?.carbs || 0) + (calorieAdjustment / 4));

  const saveAdjustment = async () => {
    if (!profile?.id) return;
    setSaving(true);
    try {
      await api.put(`/profile/${profile.id}`, {
        calorie_adjustment: calorieAdjustment,
      });
      // Update local store
      setProfile({ ...profile, calorie_adjustment: calorieAdjustment });
      Alert.alert('Saved!', 'Your macro targets have been updated.');
      router.back();
    } catch (error) {
      Alert.alert('Error', 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = calorieAdjustment !== (profile?.calorie_adjustment || 0);

  if (!macros) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Daily Targets</Text>
          <View style={{ width: 24 }} />
        </View>
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>Complete your profile to see macros</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Daily Targets</Text>
        <TouchableOpacity 
          onPress={saveAdjustment} 
          disabled={!hasChanges || saving}
          style={[styles.saveBtn, (!hasChanges || saving) && styles.saveBtnDisabled]}
        >
          {saving ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <Text style={[styles.saveBtnText, !hasChanges && styles.saveBtnTextDisabled]}>
              Save
            </Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Calorie Target */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Daily Calories</Text>
          
          <View style={styles.calorieAdjuster}>
            <TouchableOpacity 
              style={styles.adjustBtn}
              onPress={() => setCalorieAdjustment(prev => prev - 50)}
            >
              <Ionicons name="remove" size={28} color={colors.text} />
            </TouchableOpacity>
            
            <View style={styles.calorieDisplay}>
              <Text style={styles.calorieValue}>{adjustedCalories}</Text>
              {calorieAdjustment !== 0 && (
                <Text style={styles.adjustmentBadge}>
                  {calorieAdjustment > 0 ? '+' : ''}{calorieAdjustment} from base
                </Text>
              )}
            </View>
            
            <TouchableOpacity 
              style={styles.adjustBtn}
              onPress={() => setCalorieAdjustment(prev => prev + 50)}
            >
              <Ionicons name="add" size={28} color={colors.text} />
            </TouchableOpacity>
          </View>

          {/* Quick Adjust Pills */}
          <View style={styles.quickAdjustRow}>
            {[-200, -100, 0, 100, 200].map((adj) => (
              <TouchableOpacity
                key={adj}
                style={[
                  styles.quickAdjustBtn,
                  calorieAdjustment === adj && styles.quickAdjustBtnActive
                ]}
                onPress={() => setCalorieAdjustment(adj)}
              >
                <Text style={[
                  styles.quickAdjustText,
                  calorieAdjustment === adj && styles.quickAdjustTextActive
                ]}>
                  {adj === 0 ? 'Base' : adj > 0 ? `+${adj}` : adj}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.baseInfo}>
            Base: {macros.calories} cal (Mifflin-St Jeor)
          </Text>
        </View>

        {/* Macros Breakdown */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Your Macros</Text>
          
          <View style={styles.macrosGrid}>
            <View style={styles.macroItem}>
              <View style={[styles.macroIcon, { backgroundColor: '#FF6B6B20' }]}>
                <Text style={[styles.macroEmoji]}>🥩</Text>
              </View>
              <Text style={styles.macroValue}>{macros.protein}g</Text>
              <Text style={styles.macroLabel}>Protein</Text>
              <Text style={styles.macroNote}>Fixed</Text>
            </View>
            
            <View style={styles.macroItem}>
              <View style={[styles.macroIcon, { backgroundColor: '#4ECDC420' }]}>
                <Text style={styles.macroEmoji}>🍚</Text>
              </View>
              <Text style={styles.macroValue}>{adjustedCarbs}g</Text>
              <Text style={styles.macroLabel}>Carbs</Text>
              {calorieAdjustment !== 0 && (
                <Text style={[styles.macroNote, { color: '#4ECDC4' }]}>
                  {calorieAdjustment > 0 ? '+' : ''}{Math.round(calorieAdjustment / 4)}g
                </Text>
              )}
            </View>
            
            <View style={styles.macroItem}>
              <View style={[styles.macroIcon, { backgroundColor: '#FFD93D20' }]}>
                <Text style={styles.macroEmoji}>🥑</Text>
              </View>
              <Text style={styles.macroValue}>{macros.fats}g</Text>
              <Text style={styles.macroLabel}>Fats</Text>
              <Text style={styles.macroNote}>Fixed</Text>
            </View>
          </View>
        </View>

        {/* Help Guide */}
        <TouchableOpacity 
          style={styles.helpToggle}
          onPress={() => setShowGuide(!showGuide)}
        >
          <Ionicons 
            name={showGuide ? "chevron-up" : "help-circle-outline"} 
            size={20} 
            color={colors.textSecondary} 
          />
          <Text style={styles.helpToggleText}>
            {showGuide ? 'Hide guide' : 'Not seeing results? Get help'}
          </Text>
        </TouchableOpacity>

        {showGuide && (
          <View style={styles.guideCard}>
            <TouchableOpacity 
              style={styles.guideOption}
              onPress={() => setCalorieAdjustment(-200)}
            >
              <View style={[styles.guideIconWrap, { backgroundColor: '#FF6B6B20' }]}>
                <Ionicons name="trending-down" size={20} color="#FF6B6B" />
              </View>
              <View style={styles.guideContent}>
                <Text style={styles.guideTitle}>Weight not moving?</Text>
                <Text style={styles.guideDesc}>Try reducing by 100-200 cal</Text>
              </View>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={styles.guideOption}
              onPress={() => setCalorieAdjustment(0)}
            >
              <View style={[styles.guideIconWrap, { backgroundColor: '#4ECDC420' }]}>
                <Ionicons name="checkmark-circle" size={20} color="#4ECDC4" />
              </View>
              <View style={styles.guideContent}>
                <Text style={styles.guideTitle}>Progress is steady?</Text>
                <Text style={styles.guideDesc}>Keep your current target</Text>
              </View>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={styles.guideOption}
              onPress={() => setCalorieAdjustment(200)}
            >
              <View style={[styles.guideIconWrap, { backgroundColor: colors.primary + '20' }]}>
                <Ionicons name="trending-up" size={20} color={colors.primary} />
              </View>
              <View style={styles.guideContent}>
                <Text style={styles.guideTitle}>Losing too fast / low energy?</Text>
                <Text style={styles.guideDesc}>Try adding 100-200 cal</Text>
              </View>
            </TouchableOpacity>
          </View>
        )}

        {/* Info Card */}
        <View style={styles.infoCard}>
          <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
          <Text style={styles.infoText}>
            Adjustments only affect carbs. Protein and fats stay fixed to support muscle and hormones.
          </Text>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  saveBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  saveBtnDisabled: {
    opacity: 0.5,
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  saveBtnTextDisabled: {
    color: colors.textMuted,
  },
  content: {
    flex: 1,
    padding: 20,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  cardLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 16,
  },
  calorieAdjuster: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
    marginBottom: 20,
  },
  adjustBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calorieDisplay: {
    alignItems: 'center',
    minWidth: 120,
  },
  calorieValue: {
    fontSize: 48,
    fontWeight: '700',
    color: colors.primary,
  },
  adjustmentBadge: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  quickAdjustRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 16,
  },
  quickAdjustBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.surfaceLight,
  },
  quickAdjustBtnActive: {
    backgroundColor: colors.primary,
  },
  quickAdjustText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  quickAdjustTextActive: {
    color: colors.background,
  },
  baseInfo: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },
  macrosGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  macroItem: {
    alignItems: 'center',
  },
  macroIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  macroEmoji: {
    fontSize: 24,
  },
  macroValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  macroLabel: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  macroNote: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  helpToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
  },
  helpToggleText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  guideCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 12,
    gap: 8,
    marginBottom: 16,
  },
  guideOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 12,
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
  },
  guideIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  guideContent: {
    flex: 1,
  },
  guideTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  guideDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
