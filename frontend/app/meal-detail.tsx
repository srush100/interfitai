import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../src/theme/colors';
import { useUserStore } from '../src/store/userStore';
import api from '../src/services/api';

interface Meal {
  name: string;
  meal_type: string;
  ingredients: string[];
  instructions: string;
  calories: number;
  protein: number;
  carbs: number;
  fats: number;
  prep_time_minutes: number;
}

interface MealDay {
  day: string;
  meals: Meal[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fats: number;
}

interface MealPlan {
  id: string;
  name: string;
  food_preferences: string;
  supplements: string[];
  allergies: string[];
  target_calories: number;
  target_protein: number;
  target_carbs: number;
  target_fats: number;
  meal_days: MealDay[];
  created_at: string;
}

export default function MealDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { profile } = useUserStore();
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState(0);
  const [expandedMeal, setExpandedMeal] = useState<string | null>(null);
  const [generatingAlternate, setGeneratingAlternate] = useState<string | null>(null);

  useEffect(() => {
    loadMealPlan();
  }, [id]);

  const loadMealPlan = async () => {
    try {
      const response = await api.get(`/mealplan/${id}`);
      setMealPlan(response.data);
    } catch (error) {
      console.log('Error loading meal plan:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateAlternateMeal = async (dayIndex: number, mealIndex: number) => {
    if (!profile?.id || !mealPlan) return;
    
    const mealKey = `${dayIndex}-${mealIndex}`;
    setGeneratingAlternate(mealKey);
    
    try {
      const response = await api.post('/mealplan/alternate', {
        user_id: profile.id,
        meal_plan_id: mealPlan.id,
        day_index: dayIndex,
        meal_index: mealIndex,
      });
      
      const newMeal = response.data.alternate_meal;
      
      // Update the meal plan with the new meal
      const updatedPlan = { ...mealPlan };
      updatedPlan.meal_days[dayIndex].meals[mealIndex] = {
        ...newMeal,
        meal_type: mealPlan.meal_days[dayIndex].meals[mealIndex].meal_type,
      };
      setMealPlan(updatedPlan);
      
      Alert.alert('Success', `Replaced with ${newMeal.name}`);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate alternate meal');
    } finally {
      setGeneratingAlternate(null);
    }
  };

  const getMealIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'breakfast': return 'sunny';
      case 'lunch': return 'restaurant';
      case 'dinner': return 'moon';
      case 'snack': return 'nutrition';
      default: return 'fast-food';
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
      </SafeAreaView>
    );
  }

  if (!mealPlan) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>
        <Text style={styles.errorText}>Meal plan not found</Text>
      </SafeAreaView>
    );
  }

  const currentDay = mealPlan.meal_days[selectedDay];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Meal Plan</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Plan Info */}
        <View style={styles.infoCard}>
          <Text style={styles.planName}>{mealPlan.name}</Text>
          <Text style={styles.planPref}>
            {mealPlan.food_preferences.replace(/_/g, ' ')}
          </Text>

          <View style={styles.macrosRow}>
            <View style={styles.macroBox}>
              <Text style={[styles.macroValue, { color: colors.primary }]}>
                {mealPlan.target_calories}
              </Text>
              <Text style={styles.macroLabel}>Calories</Text>
            </View>
            <View style={styles.macroBox}>
              <Text style={[styles.macroValue, { color: '#FF6B6B' }]}>
                {mealPlan.target_protein}g
              </Text>
              <Text style={styles.macroLabel}>Protein</Text>
            </View>
            <View style={styles.macroBox}>
              <Text style={[styles.macroValue, { color: '#4ECDC4' }]}>
                {mealPlan.target_carbs}g
              </Text>
              <Text style={styles.macroLabel}>Carbs</Text>
            </View>
            <View style={styles.macroBox}>
              <Text style={[styles.macroValue, { color: '#FFD93D' }]}>
                {mealPlan.target_fats}g
              </Text>
              <Text style={styles.macroLabel}>Fats</Text>
            </View>
          </View>
        </View>

        {/* Day Selector */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dayTabs}>
          {mealPlan.meal_days.map((day, idx) => (
            <TouchableOpacity
              key={idx}
              style={[styles.dayTab, selectedDay === idx && styles.dayTabActive]}
              onPress={() => setSelectedDay(idx)}
            >
              <Text style={[styles.dayTabText, selectedDay === idx && styles.dayTabTextActive]}>
                Day {idx + 1}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Day Summary */}
        {currentDay && (
          <View style={styles.daySummary}>
            <Text style={styles.dayTitle}>{currentDay.day}</Text>
            <Text style={styles.dayCals}>
              {currentDay.total_calories} cal • {currentDay.total_protein}g P •{' '}
              {currentDay.total_carbs}g C • {currentDay.total_fats}g F
            </Text>
          </View>
        )}

        {/* Meals */}
        {currentDay?.meals.map((meal, mealIdx) => (
          <TouchableOpacity
            key={mealIdx}
            style={styles.mealCard}
            onPress={() =>
              setExpandedMeal(
                expandedMeal === `${selectedDay}-${mealIdx}` ? null : `${selectedDay}-${mealIdx}`
              )
            }
          >
            <View style={styles.mealHeader}>
              <View style={styles.mealIcon}>
                <Ionicons name={getMealIcon(meal.meal_type) as any} size={20} color={colors.primary} />
              </View>
              <View style={styles.mealInfo}>
                <Text style={styles.mealType}>{meal.meal_type}</Text>
                <Text style={styles.mealName}>{meal.name}</Text>
                <Text style={styles.mealMacros}>
                  {meal.calories} cal • {meal.protein}g P • {meal.carbs}g C • {meal.fats}g F
                </Text>
              </View>
              <Ionicons
                name={expandedMeal === `${selectedDay}-${mealIdx}` ? 'chevron-up' : 'chevron-down'}
                size={20}
                color={colors.textSecondary}
              />
            </View>

            {expandedMeal === `${selectedDay}-${mealIdx}` && (
              <View style={styles.mealDetails}>
                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Ingredients</Text>
                  {meal.ingredients.map((ing, ingIdx) => (
                    <Text key={ingIdx} style={styles.ingredient}>
                      • {ing}
                    </Text>
                  ))}
                </View>

                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Instructions</Text>
                  <Text style={styles.instructions}>{meal.instructions}</Text>
                </View>

                <View style={styles.prepTime}>
                  <Ionicons name="time" size={16} color={colors.textSecondary} />
                  <Text style={styles.prepTimeText}>
                    Prep time: {meal.prep_time_minutes} min
                  </Text>
                </View>

                <TouchableOpacity
                  style={styles.swapBtn}
                  onPress={() => generateAlternateMeal(selectedDay, mealIdx)}
                  disabled={generatingAlternate === `${selectedDay}-${mealIdx}`}
                >
                  {generatingAlternate === `${selectedDay}-${mealIdx}` ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <>
                      <Ionicons name="swap-horizontal" size={18} color={colors.primary} />
                      <Text style={styles.swapBtnText}>Generate Alternate</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loader: {
    flex: 1,
    justifyContent: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  errorText: {
    color: colors.text,
    textAlign: 'center',
    marginTop: 40,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  planName: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  planPref: {
    fontSize: 16,
    color: colors.primary,
    marginTop: 4,
    textTransform: 'capitalize',
  },
  macrosRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
  },
  macroBox: {
    alignItems: 'center',
  },
  macroValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  macroLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 4,
  },
  dayTabs: {
    marginBottom: 16,
  },
  dayTab: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.surface,
    marginRight: 8,
  },
  dayTabActive: {
    backgroundColor: colors.primary,
  },
  dayTabText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  dayTabTextActive: {
    color: colors.background,
  },
  daySummary: {
    marginBottom: 16,
  },
  dayTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  dayCals: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  mealCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  mealHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  mealIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  mealInfo: {
    flex: 1,
    marginLeft: 12,
  },
  mealType: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  mealName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginTop: 4,
  },
  mealMacros: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  mealDetails: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  detailSection: {
    marginBottom: 16,
  },
  detailLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  ingredient: {
    fontSize: 14,
    color: colors.text,
    marginBottom: 4,
  },
  instructions: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  prepTime: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  prepTimeText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  swapBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
    paddingVertical: 12,
    backgroundColor: colors.primary + '20',
    borderRadius: 10,
  },
  swapBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
  },
});