import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Modal,
  TextInput,
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

interface FavoriteMeal {
  id: string;
  meal_name: string;
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
  const [favoriteMeals, setFavoriteMeals] = useState<Set<string>>(new Set());
  const [savingFavorite, setSavingFavorite] = useState<string | null>(null);
  const [loggingMeal, setLoggingMeal] = useState<string | null>(null);
  const [showSwapModal, setShowSwapModal] = useState(false);
  const [swapMealTarget, setSwapMealTarget] = useState<{dayIndex: number, mealIndex: number} | null>(null);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [newPlanName, setNewPlanName] = useState('');
  const [renamingPlan, setRenamingPlan] = useState(false);

  const swapOptions = [
    { id: 'similar', label: 'Similar Macros', icon: 'swap-horizontal', description: 'Same calories & protein' },
    { id: 'higher_protein', label: 'Higher Protein', icon: 'fitness', description: 'More protein for muscle' },
    { id: 'lower_calories', label: 'Lower Calories', icon: 'trending-down', description: 'Lighter option' },
    { id: 'quick_prep', label: 'Quick Prep', icon: 'time', description: 'Under 15 minutes' },
    { id: 'vegetarian', label: 'Vegetarian', icon: 'leaf', description: 'Plant-based option' },
    { id: 'budget', label: 'Budget Friendly', icon: 'wallet', description: 'Cheaper ingredients' },
  ];

  useEffect(() => {
    loadMealPlan();
    loadFavorites();
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

  const loadFavorites = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/food/favorites/${profile.id}`);
      const favoriteNames = new Set(response.data.map((f: any) => f.meal?.name || f.meal_name));
      setFavoriteMeals(favoriteNames);
    } catch (error) {
      console.log('Error loading favorites:', error);
    }
  };

  const handleRenamePlan = async () => {
    if (!mealPlan || !newPlanName.trim()) return;
    
    setRenamingPlan(true);
    try {
      await api.put(`/mealplan/${mealPlan.id}/rename`, { name: newPlanName.trim() });
      setMealPlan({ ...mealPlan, name: newPlanName.trim() });
      setShowRenameModal(false);
      setNewPlanName('');
    } catch (error) {
      console.log('Error renaming plan:', error);
      Alert.alert('Error', 'Failed to rename meal plan');
    } finally {
      setRenamingPlan(false);
    }
  };

  const openRenameModal = () => {
    if (mealPlan) {
      setNewPlanName(mealPlan.name);
      setShowRenameModal(true);
    }
  };

  const toggleFavorite = async (meal: Meal) => {
    if (!profile?.id) return;
    
    const mealKey = meal.name;
    setSavingFavorite(mealKey);
    
    try {
      if (favoriteMeals.has(mealKey)) {
        // Find and remove the favorite
        const response = await api.get(`/food/favorites/${profile.id}`);
        const favorite = response.data.find((f: any) => (f.meal?.name || f.meal_name) === mealKey);
        if (favorite) {
          await api.delete(`/food/favorite/${favorite.id}`);
          setFavoriteMeals(prev => {
            const updated = new Set(prev);
            updated.delete(mealKey);
            return updated;
          });
        }
      } else {
        // Add to favorites
        await api.post('/food/favorite', null, {
          params: {
            user_id: profile.id,
            meal_name: meal.name,
            calories: meal.calories,
            protein: meal.protein,
            carbs: meal.carbs,
            fats: meal.fats,
            serving_size: '1 serving',
          },
        });
        setFavoriteMeals(prev => new Set([...prev, mealKey]));
      }
    } catch (error) {
      console.log('Error toggling favorite:', error);
      Alert.alert('Error', 'Failed to update favorites');
    } finally {
      setSavingFavorite(null);
    }
  };

  const logMeal = async (meal: Meal) => {
    if (!profile?.id) return;
    
    const mealKey = meal.name;
    setLoggingMeal(mealKey);
    
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: meal.name,
        serving_size: '1 serving',
        calories: meal.calories,
        protein: meal.protein,
        carbs: meal.carbs,
        fats: meal.fats,
        meal_type: meal.meal_type.toLowerCase(),
        logged_date: today,
      });
      Alert.alert('Logged!', `${meal.name} has been added to your food diary.`);
    } catch (error) {
      console.log('Error logging meal:', error);
      Alert.alert('Error', 'Failed to log meal');
    } finally {
      setLoggingMeal(null);
    }
  };

  const generateAlternateMeal = async (dayIndex: number, mealIndex: number, swapPreference: string = 'similar') => {
    if (!profile?.id || !mealPlan) return;
    
    const mealKey = `${dayIndex}-${mealIndex}`;
    setGeneratingAlternate(mealKey);
    setShowSwapModal(false);
    
    try {
      const response = await api.post('/mealplan/alternate', {
        user_id: profile.id,
        meal_plan_id: mealPlan.id,
        day_index: dayIndex,
        meal_index: mealIndex,
        swap_preference: swapPreference,
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
        <TouchableOpacity onPress={openRenameModal} style={styles.headerEditBtn}>
          <Ionicons name="create-outline" size={22} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Personalization Header */}
        <View style={styles.personalizationCard}>
          <View style={styles.personalizationHeader}>
            <Ionicons name="sparkles" size={20} color={colors.primary} />
            <View style={styles.planNameContainer}>
              <Text style={styles.personalizationTitle}>{mealPlan.name}</Text>
            </View>
          </View>
          
          {/* Rename Button - Prominent */}
          <TouchableOpacity onPress={openRenameModal} style={styles.renameButton}>
            <Ionicons name="pencil" size={16} color={colors.primary} />
            <Text style={styles.renameButtonText}>Rename Plan</Text>
          </TouchableOpacity>
          
          <Text style={styles.personalizationSubtitle}>
            Built specifically for you based on your goals and preferences
          </Text>
          
          {/* Quick Stats */}
          <View style={styles.quickStats}>
            <View style={styles.quickStat}>
              <Text style={styles.quickStatLabel}>Goal</Text>
              <Text style={styles.quickStatValue}>
                {profile?.goal?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Build Muscle'}
              </Text>
            </View>
            <View style={styles.quickStatDivider} />
            <View style={styles.quickStat}>
              <Text style={styles.quickStatLabel}>Diet Style</Text>
              <Text style={styles.quickStatValue}>
                {mealPlan.food_preferences?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Whole Foods'}
              </Text>
            </View>
            <View style={styles.quickStatDivider} />
            <View style={styles.quickStat}>
              <Text style={styles.quickStatLabel}>Meals/Day</Text>
              <Text style={styles.quickStatValue}>
                {currentDay?.meals?.length || 4}
              </Text>
            </View>
          </View>
          
          {/* Allergies Avoided */}
          {mealPlan.allergies && mealPlan.allergies.length > 0 && !mealPlan.allergies.includes('none') && (
            <View style={styles.allergiesRow}>
              <Ionicons name="shield-checkmark" size={16} color="#4ECDC4" />
              <Text style={styles.allergiesText}>
                Avoiding: {mealPlan.allergies.map(a => a.replace(/_/g, ' ')).join(', ')}
              </Text>
            </View>
          )}
        </View>

        {/* Macro Targets Card - IMPROVED */}
        <View style={styles.infoCard}>
          <Text style={styles.infoCardTitle}>Daily Targets</Text>
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

        {/* AI Explanation Card - NEW */}
        <View style={styles.aiExplanationCard}>
          <View style={styles.aiExplanationHeader}>
            <Ionicons name="bulb" size={18} color={colors.primary} />
            <Text style={styles.aiExplanationTitle}>Why This Plan Works</Text>
          </View>
          <Text style={styles.aiExplanationText}>
            {profile?.goal === 'build_muscle' || profile?.goal === 'muscle_building' ? (
              `• High protein (${mealPlan.target_protein}g) to support muscle growth and recovery\n• Adequate carbs for workout energy and glycogen replenishment\n• Balanced fats for hormone optimization`
            ) : profile?.goal === 'lose_weight' || profile?.goal === 'weight_loss' ? (
              `• Moderate calorie deficit for sustainable fat loss\n• High protein (${mealPlan.target_protein}g) to preserve muscle mass\n• Fiber-rich foods for satiety and fullness`
            ) : (
              `• Balanced macros for stable energy throughout the day\n• Adequate protein to support body composition\n• Nutrient-dense foods for overall health`
            )}
          </Text>
        </View>

        {/* Grocery List Button */}
        <TouchableOpacity
          style={styles.groceryButton}
          onPress={() => router.push(`/grocery-list?mealPlanId=${mealPlan.id}`)}
        >
          <View style={styles.groceryButtonIcon}>
            <Ionicons name="cart" size={22} color={colors.primary} />
          </View>
          <View style={styles.groceryButtonContent}>
            <Text style={styles.groceryButtonTitle}>Generate Grocery List</Text>
            <Text style={styles.groceryButtonDesc}>Get all ingredients organized by category</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
        </TouchableOpacity>

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
              
              {/* Favorite Button */}
              <TouchableOpacity
                style={styles.favoriteBtn}
                onPress={(e) => {
                  e.stopPropagation();
                  toggleFavorite(meal);
                }}
                disabled={savingFavorite === meal.name}
              >
                {savingFavorite === meal.name ? (
                  <ActivityIndicator size="small" color={colors.error} />
                ) : (
                  <Ionicons
                    name={favoriteMeals.has(meal.name) ? 'heart' : 'heart-outline'}
                    size={22}
                    color={favoriteMeals.has(meal.name) ? colors.error : colors.textSecondary}
                  />
                )}
              </TouchableOpacity>
              
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

                {/* Action Buttons Row */}
                <View style={styles.actionButtonsRow}>
                  {/* Log Meal Button */}
                  <TouchableOpacity
                    style={styles.actionBtn}
                    onPress={() => logMeal(meal)}
                    disabled={loggingMeal === meal.name}
                  >
                    {loggingMeal === meal.name ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      <>
                        <Ionicons name="add-circle" size={20} color={colors.primary} />
                        <Text style={styles.actionBtnText}>Log</Text>
                      </>
                    )}
                  </TouchableOpacity>

                  {/* Save to Favorites Button */}
                  <TouchableOpacity
                    style={styles.actionBtn}
                    onPress={() => toggleFavorite(meal)}
                    disabled={savingFavorite === meal.name}
                  >
                    {savingFavorite === meal.name ? (
                      <ActivityIndicator size="small" color={colors.error} />
                    ) : (
                      <>
                        <Ionicons 
                          name={favoriteMeals.has(meal.name) ? "heart" : "heart-outline"} 
                          size={20} 
                          color={favoriteMeals.has(meal.name) ? colors.error : colors.textSecondary} 
                        />
                        <Text style={[
                          styles.actionBtnText,
                          favoriteMeals.has(meal.name) && styles.actionBtnTextActive
                        ]}>
                          {favoriteMeals.has(meal.name) ? 'Saved' : 'Save'}
                        </Text>
                      </>
                    )}
                  </TouchableOpacity>

                  {/* Generate Alternate Button */}
                  <TouchableOpacity
                    style={styles.actionBtn}
                    onPress={() => {
                      setSwapMealTarget({ dayIndex: selectedDay, mealIndex: mealIdx });
                      setShowSwapModal(true);
                    }}
                    disabled={generatingAlternate === `${selectedDay}-${mealIdx}`}
                  >
                    {generatingAlternate === `${selectedDay}-${mealIdx}` ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      <>
                        <Ionicons name="swap-horizontal" size={20} color={colors.primary} />
                        <Text style={styles.actionBtnText}>Swap</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Smart Swap Modal */}
      <Modal
        visible={showSwapModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowSwapModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.swapModal}>
            <View style={styles.swapModalHeader}>
              <Text style={styles.swapModalTitle}>Swap Meal</Text>
              <TouchableOpacity onPress={() => setShowSwapModal(false)}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <Text style={styles.swapModalSubtitle}>What kind of alternative do you want?</Text>
            
            <ScrollView style={styles.swapOptions}>
              {swapOptions.map((option) => (
                <TouchableOpacity
                  key={option.id}
                  style={styles.swapOption}
                  onPress={() => {
                    if (swapMealTarget) {
                      generateAlternateMeal(swapMealTarget.dayIndex, swapMealTarget.mealIndex, option.id);
                    }
                  }}
                >
                  <View style={styles.swapOptionIcon}>
                    <Ionicons name={option.icon as any} size={22} color={colors.primary} />
                  </View>
                  <View style={styles.swapOptionContent}>
                    <Text style={styles.swapOptionLabel}>{option.label}</Text>
                    <Text style={styles.swapOptionDesc}>{option.description}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Rename Modal */}
      <Modal
        visible={showRenameModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowRenameModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.renameModal}>
            <Text style={styles.renameModalTitle}>Rename Meal Plan</Text>
            <TextInput
              style={styles.renameInput}
              value={newPlanName}
              onChangeText={setNewPlanName}
              placeholder="Enter new name"
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            <View style={styles.renameActions}>
              <TouchableOpacity 
                style={styles.renameCancelBtn}
                onPress={() => setShowRenameModal(false)}
              >
                <Text style={styles.renameCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.renameSaveBtn, !newPlanName.trim() && styles.renameSaveBtnDisabled]}
                onPress={handleRenamePlan}
                disabled={!newPlanName.trim() || renamingPlan}
              >
                {renamingPlan ? (
                  <ActivityIndicator size="small" color="#000" />
                ) : (
                  <Text style={styles.renameSaveText}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  headerEditBtn: {
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
  // Personalization Card Styles - NEW
  personalizationCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  personalizationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  planNameContainer: {
    flex: 1,
  },
  personalizationTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  renameButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    backgroundColor: colors.primary + '15',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 20,
    marginTop: 8,
    marginBottom: 12,
  },
  renameButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.primary,
  },
  personalizationSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  quickStats: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    padding: 12,
  },
  quickStat: {
    flex: 1,
    alignItems: 'center',
  },
  quickStatLabel: {
    fontSize: 11,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  quickStatValue: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  quickStatDivider: {
    width: 1,
    height: 30,
    backgroundColor: colors.border,
  },
  allergiesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  allergiesText: {
    fontSize: 13,
    color: '#4ECDC4',
    flex: 1,
  },
  // AI Explanation Card - NEW
  aiExplanationCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
  },
  aiExplanationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  aiExplanationTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  aiExplanationText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  // Grocery List Button
  groceryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  groceryButtonIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  groceryButtonContent: {
    flex: 1,
  },
  groceryButtonTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  groceryButtonDesc: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  infoCardTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
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
  favoriteBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 4,
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
  actionButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
    gap: 10,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 12,
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  actionBtnTextActive: {
    color: colors.error,
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
  // Smart Swap Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  swapModal: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    maxHeight: '70%',
  },
  swapModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  swapModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  swapModalSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 20,
  },
  swapOptions: {
    marginBottom: 20,
  },
  swapOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
  },
  swapOptionIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  swapOptionContent: {
    flex: 1,
  },
  swapOptionLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  swapOptionDesc: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  // Rename modal styles
  planNameContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  editIcon: {
    marginLeft: 8,
  },
  renameModal: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 30,
    width: '85%',
    maxWidth: 350,
  },
  renameModalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
    textAlign: 'center',
  },
  renameInput: {
    backgroundColor: colors.background,
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 16,
  },
  renameActions: {
    flexDirection: 'row',
    gap: 12,
  },
  renameCancelBtn: {
    flex: 1,
    paddingVertical: 12,
    backgroundColor: colors.background,
    borderRadius: 10,
    alignItems: 'center',
  },
  renameCancelText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  renameSaveBtn: {
    flex: 1,
    paddingVertical: 12,
    backgroundColor: colors.primary,
    borderRadius: 10,
    alignItems: 'center',
  },
  renameSaveBtnDisabled: {
    backgroundColor: colors.border,
  },
  renameSaveText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#000',
  },
});