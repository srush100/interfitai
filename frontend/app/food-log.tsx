import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

interface FoodEntry {
  id: string;
  food_name: string;
  serving_size: string;
  calories: number;
  protein: number;
  carbs: number;
  fats: number;
  meal_type: string;
}

interface SearchResult {
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fats: number;
}

interface FavoriteMeal {
  id: string;
  user_id: string;
  meal: {
    name: string;
    calories: number;
    protein: number;
    carbs: number;
    fats: number;
    meal_type: string;
  };
  created_at: string;
}

export default function FoodLog() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [activeTab, setActiveTab] = useState<'log' | 'search' | 'snap' | 'manual'>('log');
  const [todayLogs, setTodayLogs] = useState<FoodEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedMealType, setSelectedMealType] = useState('snack');
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [additionalContext, setAdditionalContext] = useState('');
  const [selectedSearchIdx, setSelectedSearchIdx] = useState<number | null>(null);
  const [searchQty, setSearchQty] = useState(1);
  
  // Manual entry state
  const [manualFood, setManualFood] = useState({
    name: '',
    calories: '',
    protein: '',
    carbs: '',
    fats: '',
  });
  const [energyUnit, setEnergyUnit] = useState<'cal' | 'kj'>('cal');
  const [caloriesManuallyEdited, setCaloriesManuallyEdited] = useState(false);

  // Auto-calculate calories from macros (protein=4, carbs=4, fat=9 cal/g)
  const autoCalcCalories = (protein: string, carbs: string, fats: string, unit: 'cal' | 'kj') => {
    const p = parseFloat(protein) || 0;
    const c = parseFloat(carbs) || 0;
    const f = parseFloat(fats) || 0;
    const totalCal = p * 4 + c * 4 + f * 9;
    if (totalCal === 0) return '';
    return unit === 'kj' ? Math.round(totalCal * 4.184).toString() : Math.round(totalCal).toString();
  };

  const handleMacroChange = (field: 'protein' | 'carbs' | 'fats', value: string) => {
    const updated = { ...manualFood, [field]: value };
    if (!caloriesManuallyEdited) {
      updated.calories = autoCalcCalories(
        field === 'protein' ? value : manualFood.protein,
        field === 'carbs'   ? value : manualFood.carbs,
        field === 'fats'    ? value : manualFood.fats,
        energyUnit
      );
    }
    setManualFood(updated);
  };
  
  // Saved meals state
  const [savedMeals, setSavedMeals] = useState<FavoriteMeal[]>([]);
  const [loadingSavedMeals, setLoadingSavedMeals] = useState(false);
  const [showSavedMeals, setShowSavedMeals] = useState(true);
  const [removingFavoriteId, setRemovingFavoriteId] = useState<string | null>(null);
  const [resettingLogs, setResettingLogs] = useState(false);
  const [savingSearchFavorite, setSavingSearchFavorite] = useState<number | null>(null);

  useEffect(() => {
    loadTodayLogs();
  }, [profile]);

  useEffect(() => {
    // Load saved meals when search tab is active
    if (activeTab === 'search' && profile?.id) {
      loadSavedMeals();
    }
  }, [activeTab, profile]);

  const loadTodayLogs = async () => {
    if (!profile?.id) return;
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await api.get(`/food/logs/${profile.id}?date=${today}`);
      setTodayLogs(response.data);
    } catch (error) {
      console.log('Error loading food logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSavedMeals = async () => {
    if (!profile?.id) return;
    setLoadingSavedMeals(true);
    try {
      const response = await api.get(`/food/favorites/${profile.id}`);
      setSavedMeals(response.data);
    } catch (error) {
      console.log('Error loading saved meals:', error);
    } finally {
      setLoadingSavedMeals(false);
    }
  };

  const logSavedMeal = async (meal: FavoriteMeal) => {
    if (!profile?.id) return;
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: meal.meal.name,
        serving_size: '1 serving',
        calories: meal.meal.calories,
        protein: meal.meal.protein,
        carbs: meal.meal.carbs,
        fats: meal.meal.fats,
        meal_type: selectedMealType,
        logged_date: today,
      });
      Alert.alert('Success', `${meal.meal.name} logged!`);
      loadTodayLogs();
      setActiveTab('log');
    } catch (error) {
      Alert.alert('Error', 'Failed to log meal');
    }
  };

  const removeSavedMeal = async (meal: FavoriteMeal) => {
    setRemovingFavoriteId(meal.id);
    try {
      await api.delete(`/food/favorite/${meal.id}`);
      setSavedMeals(prev => prev.filter(m => m.id !== meal.id));
    } catch (error) {
      Alert.alert('Error', 'Failed to remove saved meal');
    } finally {
      setRemovingFavoriteId(null);
    }
  };

  const saveSearchedFoodToFavorites = async (food: SearchResult, idx: number) => {
    if (!profile?.id) return;
    setSavingSearchFavorite(idx);
    try {
      await api.post('/food/favorite', null, {
        params: {
          user_id: profile.id,
          meal_name: food.name,
          calories: food.calories,
          protein: food.protein,
          carbs: food.carbs,
          fats: food.fats,
          serving_size: '1 serving',
        },
      });
      Alert.alert('Saved!', `${food.name} has been added to your favorites.`);
      // Reload saved meals to show the new item
      loadSavedMeals();
    } catch (error) {
      Alert.alert('Error', 'Failed to save to favorites');
    } finally {
      setSavingSearchFavorite(null);
    }
  };

  const resetTodayLogs = () => {
    if (todayLogs.length === 0) {
      Alert.alert('Nothing to Reset', 'No meals logged today.');
      return;
    }
    
    Alert.alert(
      'Reset Today\'s Log',
      `Are you sure you want to remove all ${todayLogs.length} logged meal${todayLogs.length > 1 ? 's' : ''}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            setResettingLogs(true);
            try {
              // Delete all logs one by one
              await Promise.all(todayLogs.map(log => api.delete(`/food/log/${log.id}`)));
              setTodayLogs([]);
              Alert.alert('Done', 'All meals have been cleared.');
            } catch (error) {
              Alert.alert('Error', 'Failed to reset logs');
              loadTodayLogs(); // Reload to get current state
            } finally {
              setResettingLogs(false);
            }
          },
        },
      ]
    );
  };

  const searchFood = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const response = await api.get(`/food/search?query=${encodeURIComponent(searchQuery)}`);
      setSearchResults(response.data);
    } catch (error) {
      console.log('Error searching food:', error);
    } finally {
      setSearching(false);
    }
  };

  const [quantity, setQuantity] = useState(1);

  const logFood = async (food: SearchResult, qty: number = 1) => {
    if (!profile?.id) return;
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: food.name,
        serving_size: qty === 1 ? '1 serving' : `${qty} servings`,
        calories: Math.round(food.calories * qty),
        protein: Math.round(food.protein * qty * 10) / 10,
        carbs: Math.round(food.carbs * qty * 10) / 10,
        fats: Math.round(food.fats * qty * 10) / 10,
        meal_type: selectedMealType,
        logged_date: today,
      });
      Alert.alert('Logged!', `${qty > 1 ? `${qty}x ` : ''}${food.name} — ${Math.round(food.calories * qty)} cal`);
      loadTodayLogs();
      setSearchQuery('');
      setSearchResults([]);
      setSelectedSearchIdx(null);
      setSearchQty(1);
      setActiveTab('log');
    } catch (error) {
      Alert.alert('Error', 'Failed to log food');
    }
  };

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera roll permissions');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      setCapturedImage(result.assets[0].base64);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera permissions');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      setCapturedImage(result.assets[0].base64);
    }
  };

  const analyzeFood = async () => {
    if (!capturedImage || !profile?.id) return;
    
    setAnalyzing(true);
    try {
      const response = await api.post('/food/analyze', {
        user_id: profile.id,
        image_base64: capturedImage,
        meal_type: selectedMealType,
        additional_context: additionalContext || undefined,
        quantity: quantity,
      });
      
      Alert.alert('Food Logged!', `${quantity}x ${response.data.food_name} - ${response.data.calories * quantity} cal`);
      setCapturedImage(null);
      setAdditionalContext('');
      setQuantity(1);
      loadTodayLogs();
      setActiveTab('log');
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to analyze food');
    } finally {
      setAnalyzing(false);
    }
  };

  const logManualFood = async () => {
    if (!profile?.id || !manualFood.name) {
      Alert.alert('Required Fields', 'Please enter a food name');
      return;
    }
    // Derive calories: if not set, auto-calc from macros
    const rawCal = parseFloat(manualFood.calories) || 0;
    const calFromMacros = (parseFloat(manualFood.protein)||0)*4 + (parseFloat(manualFood.carbs)||0)*4 + (parseFloat(manualFood.fats)||0)*9;
    let finalCalories = rawCal > 0 ? rawCal : calFromMacros;
    // Convert kJ → cal if needed
    if (energyUnit === 'kj' && finalCalories > 0) finalCalories = Math.round(finalCalories / 4.184);
    if (finalCalories === 0) {
      Alert.alert('Required Fields', 'Please enter calories or at least one macro');
      return;
    }
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: manualFood.name,
        serving_size: `${quantity} serving(s)`,
        calories: Math.round(finalCalories * quantity),
        protein: parseFloat(manualFood.protein || '0') * quantity,
        carbs: parseFloat(manualFood.carbs || '0') * quantity,
        fats: parseFloat(manualFood.fats || '0') * quantity,
        meal_type: selectedMealType,
        logged_date: today,
      });
      Alert.alert('Logged!', `${manualFood.name} — ${Math.round(finalCalories * quantity)} cal`);
      setManualFood({ name: '', calories: '', protein: '', carbs: '', fats: '' });
      setCaloriesManuallyEdited(false);
      setQuantity(1);
      loadTodayLogs();
      setActiveTab('log');
    } catch (error) {
      Alert.alert('Error', 'Failed to log food');
    }
  };

  const deleteLog = async (logId: string) => {
    Alert.alert('Delete Entry', 'Remove this food entry?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/food/log/${logId}`);
            loadTodayLogs();
          } catch (error) {
            Alert.alert('Error', 'Failed to delete entry');
          }
        },
      },
    ]);
  };

  const totalNutrition = todayLogs.reduce(
    (acc, log) => ({
      calories: acc.calories + log.calories,
      protein: acc.protein + log.protein,
      carbs: acc.carbs + log.carbs,
      fats: acc.fats + log.fats,
    }),
    { calories: 0, protein: 0, carbs: 0, fats: 0 }
  );

  const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack'];

  const renderQuantitySelector = () => (
    <View style={styles.quantityContainer}>
      <Text style={styles.quantityLabel}>Quantity</Text>
      <View style={styles.quantityControls}>
        <TouchableOpacity
          style={styles.quantityBtn}
          onPress={() => setQuantity(Math.max(1, quantity - 1))}
        >
          <Ionicons name="remove" size={20} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.quantityValue}>{quantity}</Text>
        <TouchableOpacity
          style={styles.quantityBtn}
          onPress={() => setQuantity(quantity + 1)}
        >
          <Ionicons name="add" size={20} color={colors.text} />
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Food Log</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {[
          { id: 'log', label: 'Today', icon: 'list' },
          { id: 'search', label: 'Search', icon: 'search' },
          { id: 'snap', label: 'Snap', icon: 'camera' },
          { id: 'manual', label: 'Manual', icon: 'create' },
        ].map((tab) => (
          <TouchableOpacity
            key={tab.id}
            style={[styles.tab, activeTab === tab.id && styles.tabActive]}
            onPress={() => setActiveTab(tab.id as any)}
          >
            <Ionicons
              name={tab.icon as any}
              size={20}
              color={activeTab === tab.id ? colors.primary : colors.textSecondary}
            />
            <Text style={[styles.tabText, activeTab === tab.id && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Today's Summary - ENHANCED */}
        {activeTab === 'log' && profile?.calculated_macros && (
          <View style={styles.dashboardCard}>
            {/* Calorie Ring Section */}
            <View style={styles.calorieSection}>
              <View style={styles.calorieRing}>
                <View style={[
                  styles.calorieRingProgress, 
                  { 
                    borderColor: totalNutrition.calories > ((profile.calculated_macros.calories || 0) + (profile.calorie_adjustment || 0)) 
                      ? colors.error 
                      : colors.primary 
                  }
                ]} />
                <View style={styles.calorieRingContent}>
                  <Text style={styles.calorieRingValue}>{totalNutrition.calories}</Text>
                  <Text style={styles.calorieRingLabel}>eaten</Text>
                </View>
              </View>
              <View style={styles.calorieStats}>
                <View style={styles.calorieStatRow}>
                  <Text style={styles.calorieStatLabel}>Target</Text>
                  <Text style={styles.calorieStatValue}>
                    {(profile.calculated_macros.calories || 0) + (profile.calorie_adjustment || 0)}
                  </Text>
                </View>
                <View style={styles.calorieStatRow}>
                  <Text style={styles.calorieStatLabel}>Remaining</Text>
                  <Text style={[
                    styles.calorieStatValue,
                    ((profile.calculated_macros.calories || 0) + (profile.calorie_adjustment || 0)) - totalNutrition.calories < 0 
                      ? { color: colors.error }
                      : { color: '#4ECDC4' }
                  ]}>
                    {((profile.calculated_macros.calories || 0) + (profile.calorie_adjustment || 0)) - totalNutrition.calories}
                  </Text>
                </View>
              </View>
            </View>

            {/* Macro Progress Bars */}
            <View style={styles.macroProgressSection}>
              {/* Protein */}
              <View style={styles.macroProgressItem}>
                <View style={styles.macroProgressHeader}>
                  <Text style={styles.macroProgressName}>Protein</Text>
                  <Text style={styles.macroProgressValues}>
                    {Math.round(totalNutrition.protein)}g / {profile.calculated_macros.protein}g
                  </Text>
                </View>
                <View style={styles.progressBarBg}>
                  <View style={[
                    styles.progressBarFill, 
                    { 
                      width: `${Math.min((totalNutrition.protein / (profile.calculated_macros.protein || 1)) * 100, 100)}%`,
                      backgroundColor: '#FF6B6B'
                    }
                  ]} />
                </View>
              </View>

              {/* Carbs */}
              <View style={styles.macroProgressItem}>
                <View style={styles.macroProgressHeader}>
                  <Text style={styles.macroProgressName}>Carbs</Text>
                  <Text style={styles.macroProgressValues}>
                    {Math.round(totalNutrition.carbs)}g / {Math.round((profile.calculated_macros.carbs || 0) + ((profile.calorie_adjustment || 0) / 4))}g
                  </Text>
                </View>
                <View style={styles.progressBarBg}>
                  <View style={[
                    styles.progressBarFill, 
                    { 
                      width: `${Math.min((totalNutrition.carbs / ((profile.calculated_macros.carbs || 1) + ((profile.calorie_adjustment || 0) / 4))) * 100, 100)}%`,
                      backgroundColor: '#4ECDC4'
                    }
                  ]} />
                </View>
              </View>

              {/* Fats */}
              <View style={styles.macroProgressItem}>
                <View style={styles.macroProgressHeader}>
                  <Text style={styles.macroProgressName}>Fats</Text>
                  <Text style={styles.macroProgressValues}>
                    {Math.round(totalNutrition.fats)}g / {profile.calculated_macros.fats}g
                  </Text>
                </View>
                <View style={styles.progressBarBg}>
                  <View style={[
                    styles.progressBarFill, 
                    { 
                      width: `${Math.min((totalNutrition.fats / (profile.calculated_macros.fats || 1)) * 100, 100)}%`,
                      backgroundColor: '#FFD93D'
                    }
                  ]} />
                </View>
              </View>
            </View>

            {/* AI Coach Feedback */}
            <View style={styles.aiFeedbackCard}>
              <Ionicons name="sparkles" size={16} color={colors.primary} />
              <Text style={styles.aiFeedbackText}>
                {(() => {
                  const calorieTarget = (profile.calculated_macros.calories || 0) + (profile.calorie_adjustment || 0);
                  const proteinTarget = profile.calculated_macros.protein || 0;
                  const caloriePercent = (totalNutrition.calories / calorieTarget) * 100;
                  const proteinPercent = (totalNutrition.protein / proteinTarget) * 100;
                  
                  if (todayLogs.length === 0) {
                    return "Start logging your meals to track your progress!";
                  } else if (caloriePercent >= 90 && caloriePercent <= 110 && proteinPercent >= 90) {
                    return "Great job! You're right on track with your targets today.";
                  } else if (proteinPercent < 50 && caloriePercent > 60) {
                    return "Try to prioritize protein in your remaining meals.";
                  } else if (caloriePercent > 100) {
                    return "You've exceeded your calorie target. Consider lighter options.";
                  } else if (proteinPercent >= 90) {
                    return "Excellent protein intake! You're supporting muscle recovery.";
                  } else if (caloriePercent < 50) {
                    return `You have ${Math.round(calorieTarget - totalNutrition.calories)} calories remaining today.`;
                  } else {
                    return "Keep going! You're making good progress toward your goals.";
                  }
                })()}
              </Text>
            </View>
          </View>
        )}

        {/* Log Tab */}
        {activeTab === 'log' && (
          <View style={styles.logsSection}>
            {/* Reset Button Header */}
            {todayLogs.length > 0 && (
              <View style={styles.logsSectionHeader}>
                <Text style={styles.logsSectionTitle}>{todayLogs.length} meal{todayLogs.length !== 1 ? 's' : ''} logged</Text>
                <TouchableOpacity 
                  style={styles.resetBtn}
                  onPress={resetTodayLogs}
                  disabled={resettingLogs}
                >
                  {resettingLogs ? (
                    <ActivityIndicator size="small" color={colors.error} />
                  ) : (
                    <>
                      <Ionicons name="refresh" size={16} color={colors.error} />
                      <Text style={styles.resetBtnText}>Reset</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            )}
            
            {loading ? (
              <ActivityIndicator size="large" color={colors.primary} />
            ) : todayLogs.length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="restaurant-outline" size={48} color={colors.textMuted} />
                <Text style={styles.emptyText}>No foods logged today</Text>
                <Text style={styles.emptySubtext}>Search or snap a photo to log your meals</Text>
              </View>
            ) : (
              todayLogs.map((log) => (
                <View key={log.id} style={styles.logItem}>
                  <View style={styles.logInfo}>
                    <Text style={styles.logMealType}>{log.meal_type}</Text>
                    <Text style={styles.logName}>{log.food_name}</Text>
                    <Text style={styles.logMacros}>
                      {log.calories} cal • {log.protein}g P • {log.carbs}g C • {log.fats}g F
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => deleteLog(log.id)}>
                    <Ionicons name="trash-outline" size={20} color={colors.error} />
                  </TouchableOpacity>
                </View>
              ))
            )}
          </View>
        )}

        {/* Search Tab */}
        {activeTab === 'search' && (
          <View style={styles.searchSection}>
            {/* Meal Type Selector */}
            <View style={styles.mealTypeContainer}>
              {MEAL_TYPES.map((type) => (
                <TouchableOpacity
                  key={type}
                  style={[styles.mealTypeBtn, selectedMealType === type && styles.mealTypeBtnActive]}
                  onPress={() => setSelectedMealType(type)}
                >
                  <Text style={[styles.mealTypeText, selectedMealType === type && styles.mealTypeTextActive]}>
                    {type}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Saved Meals Section */}
            {savedMeals.length > 0 && (
              <View style={styles.savedMealsSection}>
                <TouchableOpacity 
                  style={styles.savedMealsHeader}
                  onPress={() => setShowSavedMeals(!showSavedMeals)}
                >
                  <View style={styles.savedMealsHeaderLeft}>
                    <Ionicons name="heart" size={18} color={colors.error} />
                    <Text style={styles.savedMealsTitle}>Saved Meals</Text>
                    <View style={styles.savedMealsBadge}>
                      <Text style={styles.savedMealsBadgeText}>{savedMeals.length}</Text>
                    </View>
                  </View>
                  <Ionicons 
                    name={showSavedMeals ? 'chevron-up' : 'chevron-down'} 
                    size={20} 
                    color={colors.textSecondary} 
                  />
                </TouchableOpacity>
                
                {showSavedMeals && (
                  <View style={styles.savedMealsList}>
                    {loadingSavedMeals ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      savedMeals.map((savedMeal) => (
                        <View key={savedMeal.id} style={styles.savedMealItem}>
                          <TouchableOpacity
                            style={styles.savedMealContent}
                            onPress={() => logSavedMeal(savedMeal)}
                          >
                            <View style={styles.savedMealInfo}>
                              <Text style={styles.savedMealName}>{savedMeal.meal.name}</Text>
                              <Text style={styles.savedMealMacros}>
                                {savedMeal.meal.calories} cal • {savedMeal.meal.protein}g P • {savedMeal.meal.carbs}g C • {savedMeal.meal.fats}g F
                              </Text>
                            </View>
                            <Ionicons name="add-circle" size={24} color={colors.primary} />
                          </TouchableOpacity>
                          <TouchableOpacity
                            style={styles.unsaveBtn}
                            onPress={() => removeSavedMeal(savedMeal)}
                            disabled={removingFavoriteId === savedMeal.id}
                          >
                            {removingFavoriteId === savedMeal.id ? (
                              <ActivityIndicator size="small" color={colors.error} />
                            ) : (
                              <Ionicons name="heart-dislike" size={18} color={colors.error} />
                            )}
                          </TouchableOpacity>
                        </View>
                      ))
                    )}
                  </View>
                )}
              </View>
            )}

            {/* Divider with "or search" text */}
            <View style={styles.dividerContainer}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or search food database</Text>
              <View style={styles.dividerLine} />
            </View>

            <View style={styles.searchBar}>
              <Ionicons name="search" size={20} color={colors.textMuted} />
              <TextInput
                style={styles.searchInput}
                placeholder="Search for food..."
                placeholderTextColor={colors.textMuted}
                value={searchQuery}
                onChangeText={setSearchQuery}
                onSubmitEditing={searchFood}
                returnKeyType="search"
              />
              {searchQuery && (
                <TouchableOpacity onPress={() => setSearchQuery('')}>
                  <Ionicons name="close-circle" size={20} color={colors.textMuted} />
                </TouchableOpacity>
              )}
            </View>

            <TouchableOpacity style={styles.searchBtn} onPress={searchFood} disabled={searching}>
              {searching ? (
                <ActivityIndicator size="small" color={colors.background} />
              ) : (
                <Text style={styles.searchBtnText}>Search</Text>
              )}
            </TouchableOpacity>

            {searchResults.length > 0 && (
              <View style={styles.resultsContainer}>
                {searchResults.map((food, idx) => {
                  const isSelected = selectedSearchIdx === idx;
                  const qty = isSelected ? searchQty : 1;
                  return (
                    <View key={idx} style={[styles.resultItem, isSelected && styles.resultItemExpanded]}>
                      {/* Food name row — tap to expand/collapse */}
                      <TouchableOpacity
                        style={styles.resultContent}
                        onPress={() => {
                          if (isSelected) {
                            setSelectedSearchIdx(null);
                            setSearchQty(1);
                          } else {
                            setSelectedSearchIdx(idx);
                            setSearchQty(1);
                          }
                        }}
                        activeOpacity={0.7}
                      >
                        <View style={styles.resultInfo}>
                          <Text style={styles.resultName}>{food.name}</Text>
                          <Text style={styles.resultMacros}>
                            {isSelected
                              ? `${Math.round(food.calories * qty)} cal • ${Math.round(food.protein * qty * 10) / 10}g P • ${Math.round(food.carbs * qty * 10) / 10}g C • ${Math.round(food.fats * qty * 10) / 10}g F`
                              : `${food.calories} cal • ${food.protein}g P • ${food.carbs}g C • ${food.fats}g F`}
                          </Text>
                        </View>
                        <Ionicons
                          name={isSelected ? 'chevron-up' : 'add-circle'}
                          size={26}
                          color={colors.primary}
                        />
                      </TouchableOpacity>

                      {/* Inline quantity + add row — only shown when expanded */}
                      {isSelected && (
                        <View style={styles.inlineQtyRow}>
                          <View style={styles.inlineQtyControls}>
                            <TouchableOpacity
                              style={[styles.inlineQtyBtn, searchQty <= 1 && styles.inlineQtyBtnDisabled]}
                              onPress={() => setSearchQty(q => Math.max(1, q - 1))}
                              disabled={searchQty <= 1}
                            >
                              <Ionicons name="remove" size={18} color={searchQty <= 1 ? colors.textSecondary : colors.text} />
                            </TouchableOpacity>
                            <Text style={styles.inlineQtyValue}>{searchQty}</Text>
                            <TouchableOpacity
                              style={[styles.inlineQtyBtn, searchQty >= 10 && styles.inlineQtyBtnDisabled]}
                              onPress={() => setSearchQty(q => Math.min(10, q + 1))}
                              disabled={searchQty >= 10}
                            >
                              <Ionicons name="add" size={18} color={searchQty >= 10 ? colors.textSecondary : colors.text} />
                            </TouchableOpacity>
                          </View>

                          <TouchableOpacity
                            style={styles.inlineAddBtn}
                            onPress={() => logFood(food, searchQty)}
                          >
                            <Text style={styles.inlineAddBtnText}>
                              Add {searchQty > 1 ? `×${searchQty}` : ''}
                            </Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {/* Save to favourites — always visible */}
                      {!isSelected && (
                        <TouchableOpacity
                          style={styles.saveFavoriteBtn}
                          onPress={() => saveSearchedFoodToFavorites(food, idx)}
                          disabled={savingSearchFavorite === idx}
                        >
                          {savingSearchFavorite === idx ? (
                            <ActivityIndicator size="small" color={colors.primary} />
                          ) : (
                            <Ionicons name="heart-outline" size={20} color={colors.primary} />
                          )}
                        </TouchableOpacity>
                      )}
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        )}

        {/* Snap Tab */}
        {activeTab === 'snap' && (
          <View style={styles.snapSection}>
            {/* Meal Type Selector */}
            <View style={styles.mealTypeContainer}>
              {MEAL_TYPES.map((type) => (
                <TouchableOpacity
                  key={type}
                  style={[styles.mealTypeBtn, selectedMealType === type && styles.mealTypeBtnActive]}
                  onPress={() => setSelectedMealType(type)}
                >
                  <Text style={[styles.mealTypeText, selectedMealType === type && styles.mealTypeTextActive]}>
                    {type}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {capturedImage ? (
              <View style={styles.previewContainer}>
                <Image
                  source={{ uri: `data:image/jpeg;base64,${capturedImage}` }}
                  style={styles.previewImage}
                />
                
                {/* Additional Context Input */}
                <TextInput
                  style={styles.contextInput}
                  placeholder="Add context (e.g., '2 eggs, half portion')"
                  placeholderTextColor={colors.textMuted}
                  value={additionalContext}
                  onChangeText={setAdditionalContext}
                  multiline
                />
                
                {/* Quantity Selector */}
                {renderQuantitySelector()}
                
                <View style={styles.previewActions}>
                  <TouchableOpacity
                    style={styles.retakeBtn}
                    onPress={() => {
                      setCapturedImage(null);
                      setAdditionalContext('');
                      setQuantity(1);
                    }}
                  >
                    <Ionicons name="refresh" size={20} color={colors.text} />
                    <Text style={styles.retakeBtnText}>Retake</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.analyzeBtn}
                    onPress={analyzeFood}
                    disabled={analyzing}
                  >
                    {analyzing ? (
                      <ActivityIndicator size="small" color={colors.background} />
                    ) : (
                      <>
                        <Ionicons name="sparkles" size={20} color={colors.background} />
                        <Text style={styles.analyzeBtnText}>Analyze & Log</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <View style={styles.captureContainer}>
                <View style={styles.captureIcon}>
                  <Ionicons name="camera" size={64} color={colors.primary} />
                </View>
                <Text style={styles.captureTitle}>Snap Your Food</Text>
                <Text style={styles.captureSubtitle}>
                  Take a photo and our AI will identify the food and estimate nutrition
                </Text>
                <View style={styles.captureButtons}>
                  <TouchableOpacity style={styles.captureBtn} onPress={takePhoto}>
                    <Ionicons name="camera" size={24} color={colors.background} />
                    <Text style={styles.captureBtnText}>Take Photo</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.galleryBtn} onPress={pickImage}>
                    <Ionicons name="images" size={24} color={colors.primary} />
                    <Text style={styles.galleryBtnText}>Gallery</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>
        )}

        {/* Manual Entry Tab */}
        {activeTab === 'manual' && (
          <View style={styles.manualSection}>
            {/* Meal Type Selector */}
            <View style={styles.mealTypeContainer}>
              {MEAL_TYPES.map((type) => (
                <TouchableOpacity
                  key={type}
                  style={[styles.mealTypeBtn, selectedMealType === type && styles.mealTypeBtnActive]}
                  onPress={() => setSelectedMealType(type)}
                >
                  <Text style={[styles.mealTypeText, selectedMealType === type && styles.mealTypeTextActive]}>
                    {type}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.manualLabel}>Food Name *</Text>
            <TextInput
              style={styles.manualInput}
              placeholder="e.g., Grilled Chicken Breast"
              placeholderTextColor={colors.textMuted}
              value={manualFood.name}
              onChangeText={(text) => setManualFood({ ...manualFood, name: text })}
            />

            {/* Energy row: label + cal/kj toggle */}
            <View style={styles.energyHeader}>
              <Text style={styles.manualLabel}>Energy</Text>
              <View style={styles.unitToggle}>
                <TouchableOpacity
                  style={[styles.unitBtn, energyUnit === 'cal' && styles.unitBtnActive]}
                  onPress={() => {
                    if (energyUnit !== 'cal') {
                      setEnergyUnit('cal');
                      // Convert existing value kJ → cal
                      if (manualFood.calories) {
                        setManualFood(f => ({ ...f, calories: Math.round(parseFloat(f.calories) / 4.184).toString() }));
                      }
                    }
                  }}
                >
                  <Text style={[styles.unitBtnText, energyUnit === 'cal' && styles.unitBtnTextActive]}>cal</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.unitBtn, energyUnit === 'kj' && styles.unitBtnActive]}
                  onPress={() => {
                    if (energyUnit !== 'kj') {
                      setEnergyUnit('kj');
                      // Convert existing value cal → kJ
                      if (manualFood.calories) {
                        setManualFood(f => ({ ...f, calories: Math.round(parseFloat(f.calories) * 4.184).toString() }));
                      }
                    }
                  }}
                >
                  <Text style={[styles.unitBtnText, energyUnit === 'kj' && styles.unitBtnTextActive]}>kJ</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Calories/kJ input with auto badge */}
            <View style={styles.caloriesInputRow}>
              <TextInput
                style={[styles.manualInput, styles.caloriesInput]}
                placeholder={energyUnit === 'cal' ? 'e.g. 250' : 'e.g. 1046'}
                placeholderTextColor={colors.textMuted}
                value={manualFood.calories}
                onChangeText={(text) => {
                  setCaloriesManuallyEdited(true);
                  setManualFood({ ...manualFood, calories: text });
                }}
                keyboardType="numeric"
              />
              {!caloriesManuallyEdited && manualFood.calories !== '' && (
                <View style={styles.autoBadge}>
                  <Ionicons name="flash" size={11} color={colors.primary} />
                  <Text style={styles.autoBadgeText}>auto</Text>
                </View>
              )}
            </View>

            <View style={styles.macroRow}>
              <View style={styles.macroInputContainer}>
                <Text style={[styles.manualLabel, { color: '#FF6B6B' }]}>Protein (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.protein}
                  onChangeText={(text) => handleMacroChange('protein', text)}
                  keyboardType="numeric"
                />
              </View>
              <View style={styles.macroInputContainer}>
                <Text style={[styles.manualLabel, { color: '#4ECDC4' }]}>Carbs (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.carbs}
                  onChangeText={(text) => handleMacroChange('carbs', text)}
                  keyboardType="numeric"
                />
              </View>
              <View style={styles.macroInputContainer}>
                <Text style={[styles.manualLabel, { color: '#F97316' }]}>Fats (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.fats}
                  onChangeText={(text) => handleMacroChange('fats', text)}
                  keyboardType="numeric"
                />
              </View>
            </View>

            {/* Quantity Selector */}
            {renderQuantitySelector()}

            <TouchableOpacity style={styles.manualBtn} onPress={logManualFood}>
              <Ionicons name="add-circle" size={22} color={colors.background} />
              <Text style={styles.manualBtnText}>Log Food</Text>
            </TouchableOpacity>
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
  tabs: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 8,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  tabActive: {
    backgroundColor: colors.primary + '20',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.primary,
  },
  scrollContent: {
    padding: 20,
    paddingTop: 0,
    paddingBottom: 40,
  },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  summaryItem: {
    alignItems: 'center',
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  summaryLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  // Enhanced Dashboard Styles
  dashboardCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  calorieSection: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  calorieRing: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  calorieRingProgress: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 50,
    borderWidth: 6,
    borderColor: colors.primary,
  },
  calorieRingContent: {
    alignItems: 'center',
  },
  calorieRingValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  calorieRingLabel: {
    fontSize: 11,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  calorieStats: {
    flex: 1,
    marginLeft: 20,
    gap: 12,
  },
  calorieStatRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  calorieStatLabel: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  calorieStatValue: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  macroProgressSection: {
    gap: 12,
    marginBottom: 16,
  },
  macroProgressItem: {
    gap: 6,
  },
  macroProgressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  macroProgressName: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  macroProgressValues: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  progressBarBg: {
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceLight,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  aiFeedbackCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.primary + '15',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  aiFeedbackText: {
    flex: 1,
    fontSize: 13,
    color: colors.text,
    lineHeight: 18,
  },
  targetVsConsumed: {
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  targetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  targetLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  targetValues: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  remainingText: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
  },
  logsSection: {
    gap: 12,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  logItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
  },
  logInfo: {
    flex: 1,
  },
  logMealType: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.primary,
    textTransform: 'uppercase',
  },
  logName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginTop: 4,
  },
  logMacros: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  searchSection: {
    gap: 16,
  },
  mealTypeContainer: {
    flexDirection: 'row',
    gap: 8,
  },
  mealTypeBtn: {
    flex: 1,
    padding: 10,
    borderRadius: 8,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  mealTypeBtnActive: {
    backgroundColor: colors.primary + '20',
  },
  mealTypeText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  mealTypeTextActive: {
    color: colors.primary,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 16,
    gap: 12,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.text,
  },
  searchBtn: {
    backgroundColor: colors.primary,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  searchBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  resultsContainer: {
    gap: 10,
  },
  resultItem: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    marginBottom: 2,
    overflow: 'hidden',
  },
  resultItemExpanded: {
    borderWidth: 1,
    borderColor: colors.primary,
  },
  inlineQtyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  inlineQtyControls: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: 10,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
  },
  inlineQtyBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inlineQtyBtnDisabled: {
    opacity: 0.4,
  },
  inlineQtyValue: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.text,
    minWidth: 36,
    textAlign: 'center',
  },
  inlineAddBtn: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingHorizontal: 22,
    paddingVertical: 10,
  },
  inlineAddBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.background,
  },
  resultContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    gap: 10,
  },
  resultInfo: {
    flex: 1,
  },
  resultName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  resultMacros: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 3,
  },
  saveFavoriteBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.primary + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  snapSection: {
    gap: 16,
  },
  captureContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  captureIcon: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginTop: 24,
  },
  captureSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 20,
  },
  captureButtons: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 32,
  },
  captureBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 28,
  },
  captureBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  galleryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  galleryBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  previewContainer: {
    alignItems: 'center',
  },
  previewImage: {
    width: 250,
    height: 250,
    borderRadius: 16,
  },
  previewActions: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 24,
  },
  retakeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 28,
  },
  retakeBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 28,
  },
  analyzeBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  quantityContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
    marginTop: 16,
  },
  quantityLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  quantityControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  quantityBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  quantityValue: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    minWidth: 24,
    textAlign: 'center',
  },
  contextInput: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    fontSize: 15,
    color: colors.text,
    minHeight: 60,
    textAlignVertical: 'top',
  },
  energyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
    marginTop: 8,
  },
  unitToggle: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 8,
    padding: 2,
    gap: 2,
  },
  unitBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 6,
  },
  unitBtnActive: {
    backgroundColor: colors.primary,
  },
  unitBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  unitBtnTextActive: {
    color: colors.background,
  },
  caloriesInputRow: {
    position: 'relative',
    marginBottom: 12,
  },
  caloriesInput: {
    marginBottom: 0,
  },
  autoBadge: {
    position: 'absolute',
    right: 12,
    top: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  autoBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.primary,
  },
  manualInput: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    fontSize: 15,
    color: colors.text,
  },
  manualLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: 16,
  },
  manualBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: colors.primary,
    padding: 16,
    borderRadius: 16,
    marginTop: 24,
  },
  manualBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.background,
  },
  macroRow: {
    flexDirection: 'row',
    gap: 12,
  },
  macroInputContainer: {
    flex: 1,
  },
  // Saved meals styles
  savedMealsSection: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
  },
  savedMealsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
  },
  savedMealsHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  savedMealsTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  savedMealsBadge: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    minWidth: 22,
    alignItems: 'center',
  },
  savedMealsBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.background,
  },
  savedMealsList: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingVertical: 4,
  },
  savedMealItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    gap: 8,
  },
  savedMealContent: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  savedMealInfo: {
    flex: 1,
  },
  savedMealName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  savedMealMacros: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  unsaveBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.error + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Divider styles
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    fontSize: 13,
    color: colors.textMuted,
  },
  // Logs section header
  logsSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  logsSectionTitle: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: colors.error + '15',
  },
  resetBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.error,
  },
});