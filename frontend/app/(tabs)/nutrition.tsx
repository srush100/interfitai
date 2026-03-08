import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

interface MealPlan {
  id: string;
  name: string;
  food_preferences: string;
  target_calories: number;
  target_protein: number;
  created_at: string;
}

export default function NutritionScreen() {
  const router = useRouter();
  const { profile, loadProfile } = useUserStore();
  const [mealPlans, setMealPlans] = useState<MealPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dailySummary, setDailySummary] = useState<any>(null);

  // Reload profile when screen comes into focus (to get latest calorie_adjustment)
  useFocusEffect(
    useCallback(() => {
      loadProfile();
      loadData();
    }, [])
  );

  useEffect(() => {
    loadData();
  }, [profile]);

  const loadData = async () => {
    if (!profile?.id) return;
    try {
      const [plansRes, summaryRes] = await Promise.all([
        api.get(`/mealplans/${profile.id}`),
        api.get(`/food/daily-summary/${profile.id}/${new Date().toISOString().split('T')[0]}`),
      ]);
      setMealPlans(plansRes.data);
      setDailySummary(summaryRes.data);
    } catch (error) {
      console.log('Error loading nutrition data:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const deleteMealPlan = async (planId: string) => {
    Alert.alert(
      'Delete Meal Plan',
      'Are you sure you want to delete this meal plan?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/mealplan/${planId}`);
              setMealPlans(mealPlans.filter((p) => p.id !== planId));
            } catch (error) {
              Alert.alert('Error', 'Failed to delete meal plan');
            }
          },
        },
      ]
    );
  };

  const macros = profile?.calculated_macros;
  const consumed = dailySummary?.consumed || {};
  
  // Apply calorie adjustment (only affects carbs, protein and fats stay fixed)
  const calorieAdjustment = profile?.calorie_adjustment || 0;
  const adjustedCalories = (macros?.calories || 0) + calorieAdjustment;
  const adjustedCarbs = Math.round((macros?.carbs || 0) + (calorieAdjustment / 4));

  const getProgress = (current: number, target: number) => {
    return Math.min((current / target) * 100, 100);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Nutrition</Text>
        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => router.push('/meal-questionnaire')}
        >
          <Ionicons name="add" size={24} color={colors.background} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
      >
        {/* Today's Progress */}
        {macros && (
          <View style={styles.progressCard}>
            <View style={styles.progressHeader}>
              <Text style={styles.progressTitle}>Today's Progress</Text>
              <TouchableOpacity onPress={() => router.push('/food-log')}>
                <Text style={styles.viewAll}>Log Food</Text>
              </TouchableOpacity>
            </View>

            {/* Calories */}
            <View style={styles.caloriesRow}>
              <View style={styles.caloriesInfo}>
                <Text style={styles.caloriesValue}>{consumed.calories || 0}</Text>
                <Text style={styles.caloriesLabel}>/ {adjustedCalories} cal</Text>
              </View>
              <View style={styles.caloriesRing}>
                <Text style={styles.ringText}>
                  {Math.round(getProgress(consumed.calories || 0, adjustedCalories))}%
                </Text>
              </View>
            </View>

            {/* Macros Progress */}
            <View style={styles.macrosProgress}>
              <View style={styles.macroProgress}>
                <View style={styles.macroHeader}>
                  <Text style={styles.macroName}>Protein</Text>
                  <Text style={styles.macroValues}>
                    {Math.round(consumed.protein || 0)}g / {macros.protein}g
                  </Text>
                </View>
                <View style={styles.progressBar}>
                  <View
                    style={[
                      styles.progressFill,
                      { width: `${getProgress(consumed.protein || 0, macros.protein)}%`, backgroundColor: '#FF6B6B' },
                    ]}
                  />
                </View>
              </View>

              <View style={styles.macroProgress}>
                <View style={styles.macroHeader}>
                  <Text style={styles.macroName}>Carbs</Text>
                  <Text style={styles.macroValues}>
                    {Math.round(consumed.carbs || 0)}g / {adjustedCarbs}g
                  </Text>
                </View>
                <View style={styles.progressBar}>
                  <View
                    style={[
                      styles.progressFill,
                      { width: `${getProgress(consumed.carbs || 0, adjustedCarbs)}%`, backgroundColor: '#4ECDC4' },
                    ]}
                  />
                </View>
              </View>

              <View style={styles.macroProgress}>
                <View style={styles.macroHeader}>
                  <Text style={styles.macroName}>Fats</Text>
                  <Text style={styles.macroValues}>
                    {Math.round(consumed.fats || 0)}g / {macros.fats}g
                  </Text>
                </View>
                <View style={styles.progressBar}>
                  <View
                    style={[
                      styles.progressFill,
                      { width: `${getProgress(consumed.fats || 0, macros.fats)}%`, backgroundColor: '#FFD93D' },
                    ]}
                  />
                </View>
              </View>
            </View>
          </View>
        )}

        {/* Quick Actions */}
        <View style={styles.quickActions}>
          <TouchableOpacity
            style={styles.quickAction}
            onPress={() => router.push('/food-log')}
          >
            <Ionicons name="camera" size={24} color={colors.primary} />
            <Text style={styles.quickActionText}>Snap Food</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.quickAction}
            onPress={() => router.push('/food-log')}
          >
            <Ionicons name="search" size={24} color={colors.primary} />
            <Text style={styles.quickActionText}>Search Food</Text>
          </TouchableOpacity>
        </View>

        {/* Create Meal Plan CTA */}
        <TouchableOpacity
          style={styles.createCard}
          onPress={() => router.push('/meal-questionnaire')}
        >
          <View style={styles.createIcon}>
            <Ionicons name="restaurant" size={32} color={colors.primary} />
          </View>
          <View style={styles.createContent}>
            <Text style={styles.createTitle}>Create Meal Plan</Text>
            <Text style={styles.createSubtitle}>
              AI-generated meals based on your macros
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color={colors.primary} />
        </TouchableOpacity>

        {/* Meal Plans List */}
        {loading ? (
          <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
        ) : mealPlans.length > 0 && (
          <View style={styles.plansList}>
            <Text style={styles.sectionTitle}>Your Meal Plans</Text>
            {mealPlans.map((plan) => (
              <TouchableOpacity
                key={plan.id}
                style={styles.planCard}
                onPress={() => router.push(`/meal-detail?id=${plan.id}`)}
              >
                <View style={styles.planHeader}>
                  <View>
                    <Text style={styles.planName}>{plan.name}</Text>
                    <Text style={styles.planMeta}>
                      {plan.target_calories} cal • {plan.target_protein}g protein
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => deleteMealPlan(plan.id)}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  >
                    <Ionicons name="trash-outline" size={20} color={colors.error} />
                  </TouchableOpacity>
                </View>
                <View style={styles.planTags}>
                  <View style={styles.tag}>
                    <Text style={styles.tagText}>{plan.food_preferences}</Text>
                  </View>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
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
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingBottom: 0,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  addBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 100,
  },
  progressCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginBottom: 16,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  progressTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  viewAll: {
    fontSize: 14,
    color: colors.primary,
    fontWeight: '600',
  },
  caloriesRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  caloriesInfo: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  caloriesValue: {
    fontSize: 36,
    fontWeight: '700',
    color: colors.primary,
  },
  caloriesLabel: {
    fontSize: 16,
    color: colors.textSecondary,
    marginLeft: 8,
  },
  caloriesRing: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 4,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  ringText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.text,
  },
  macrosProgress: {
    gap: 12,
  },
  macroProgress: {
    gap: 6,
  },
  macroHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  macroName: {
    fontSize: 14,
    color: colors.text,
    fontWeight: '500',
  },
  macroValues: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  progressBar: {
    height: 8,
    backgroundColor: colors.surfaceLight,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  quickActions: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  quickAction: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  quickActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  createCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginBottom: 24,
    borderWidth: 2,
    borderColor: colors.primary,
    borderStyle: 'dashed',
  },
  createIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  createContent: {
    flex: 1,
    marginLeft: 16,
  },
  createTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  createSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  loader: {
    marginTop: 20,
  },
  plansList: {
    gap: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  planCard: {
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 16,
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  planName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  planMeta: {
    fontSize: 14,
    color: colors.primary,
    marginTop: 4,
  },
  planTags: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  tag: {
    backgroundColor: colors.surfaceLight,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  tagText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
});