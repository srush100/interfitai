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
  const [quantity, setQuantity] = useState(1);
  
  // Manual entry state
  const [manualFood, setManualFood] = useState({
    name: '',
    calories: '',
    protein: '',
    carbs: '',
    fats: '',
  });
  
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

  const logFood = async (food: SearchResult) => {
    if (!profile?.id) return;
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: food.name,
        serving_size: '1 serving',
        calories: food.calories,
        protein: food.protein,
        carbs: food.carbs,
        fats: food.fats,
        meal_type: selectedMealType,
        logged_date: today,
      });
      Alert.alert('Success', `${food.name} logged!`);
      loadTodayLogs();
      setSearchQuery('');
      setSearchResults([]);
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
    if (!profile?.id || !manualFood.name || !manualFood.calories) {
      Alert.alert('Required Fields', 'Please enter food name and calories');
      return;
    }
    
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: manualFood.name,
        serving_size: `${quantity} serving(s)`,
        calories: parseInt(manualFood.calories) * quantity,
        protein: parseFloat(manualFood.protein || '0') * quantity,
        carbs: parseFloat(manualFood.carbs || '0') * quantity,
        fats: parseFloat(manualFood.fats || '0') * quantity,
        meal_type: selectedMealType,
        logged_date: today,
      });
      
      Alert.alert('Success', `${manualFood.name} logged!`);
      setManualFood({ name: '', calories: '', protein: '', carbs: '', fats: '' });
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
        {/* Today's Summary */}
        {activeTab === 'log' && (
          <View style={styles.summaryCard}>
            <Text style={styles.summaryTitle}>Today's Totals</Text>
            <View style={styles.summaryRow}>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryValue, { color: colors.primary }]}>
                  {totalNutrition.calories}
                </Text>
                <Text style={styles.summaryLabel}>Calories</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryValue, { color: '#FF6B6B' }]}>
                  {Math.round(totalNutrition.protein)}g
                </Text>
                <Text style={styles.summaryLabel}>Protein</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryValue, { color: '#4ECDC4' }]}>
                  {Math.round(totalNutrition.carbs)}g
                </Text>
                <Text style={styles.summaryLabel}>Carbs</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={[styles.summaryValue, { color: '#FFD93D' }]}>
                  {Math.round(totalNutrition.fats)}g
                </Text>
                <Text style={styles.summaryLabel}>Fats</Text>
              </View>
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
                {searchResults.map((food, idx) => (
                  <View key={idx} style={styles.resultItem}>
                    <TouchableOpacity
                      style={styles.resultContent}
                      onPress={() => logFood(food)}
                    >
                      <View style={styles.resultInfo}>
                        <Text style={styles.resultName}>{food.name}</Text>
                        <Text style={styles.resultMacros}>
                          {food.calories} cal • {food.protein}g P • {food.carbs}g C • {food.fats}g F
                        </Text>
                      </View>
                      <Ionicons name="add-circle" size={26} color={colors.primary} />
                    </TouchableOpacity>
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
                  </View>
                ))}
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

            <Text style={styles.manualLabel}>Calories *</Text>
            <TextInput
              style={styles.manualInput}
              placeholder="e.g., 250"
              placeholderTextColor={colors.textMuted}
              value={manualFood.calories}
              onChangeText={(text) => setManualFood({ ...manualFood, calories: text })}
              keyboardType="numeric"
            />

            <View style={styles.macroRow}>
              <View style={styles.macroInputContainer}>
                <Text style={styles.manualLabel}>Protein (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.protein}
                  onChangeText={(text) => setManualFood({ ...manualFood, protein: text })}
                  keyboardType="numeric"
                />
              </View>
              <View style={styles.macroInputContainer}>
                <Text style={styles.manualLabel}>Carbs (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.carbs}
                  onChangeText={(text) => setManualFood({ ...manualFood, carbs: text })}
                  keyboardType="numeric"
                />
              </View>
              <View style={styles.macroInputContainer}>
                <Text style={styles.manualLabel}>Fats (g)</Text>
                <TextInput
                  style={styles.manualInput}
                  placeholder="0"
                  placeholderTextColor={colors.textMuted}
                  value={manualFood.fats}
                  onChangeText={(text) => setManualFood({ ...manualFood, fats: text })}
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
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 14,
    borderRadius: 12,
    gap: 10,
  },
  resultContent: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
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
  manualSection: {
    gap: 4,
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