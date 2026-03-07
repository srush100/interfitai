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
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../src/theme/colors';
import { useUserStore } from '../src/store/userStore';
import api from '../src/services/api';

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

export default function SavedMeals() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [favorites, setFavorites] = useState<FavoriteMeal[]>([]);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState<string | null>(null);

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/food/favorites/${profile.id}`);
      setFavorites(response.data);
    } catch (error) {
      console.log('Error loading favorites:', error);
    } finally {
      setLoading(false);
    }
  };

  const removeFavorite = async (favorite: FavoriteMeal) => {
    Alert.alert(
      'Remove Favorite',
      `Remove "${favorite.meal.name}" from your favorites?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setRemovingId(favorite.id);
            try {
              await api.delete(`/food/favorite/${favorite.id}`);
              setFavorites(prev => prev.filter(f => f.id !== favorite.id));
            } catch (error) {
              Alert.alert('Error', 'Failed to remove favorite');
            } finally {
              setRemovingId(null);
            }
          },
        },
      ]
    );
  };

  const logMealFromFavorite = async (favorite: FavoriteMeal) => {
    if (!profile?.id) return;
    
    try {
      const today = new Date().toISOString().split('T')[0];
      await api.post('/food/log', {
        user_id: profile.id,
        food_name: favorite.meal.name,
        calories: favorite.meal.calories,
        protein: favorite.meal.protein,
        carbs: favorite.meal.carbs,
        fats: favorite.meal.fats,
        serving_size: '1 serving',
        meal_type: 'snack',
        logged_date: today,
      });
      Alert.alert('Success', `${favorite.meal.name} logged to your food diary!`);
    } catch (error) {
      Alert.alert('Error', 'Failed to log meal');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Saved Meals</Text>
          <View style={styles.backBtn} />
        </View>
        <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Saved Meals</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {favorites.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="heart-outline" size={64} color={colors.textMuted} />
            <Text style={styles.emptyTitle}>No Saved Meals</Text>
            <Text style={styles.emptyText}>
              Tap the heart icon on any meal in your meal plan to save it here for quick access.
            </Text>
          </View>
        ) : (
          <>
            <Text style={styles.countText}>{favorites.length} saved meal{favorites.length !== 1 ? 's' : ''}</Text>
            
            {favorites.map((favorite) => (
              <View key={favorite.id} style={styles.mealCard}>
                <View style={styles.mealHeader}>
                  <View style={styles.mealIcon}>
                    <Ionicons name="heart" size={20} color={colors.error} />
                  </View>
                  <View style={styles.mealInfo}>
                    <Text style={styles.mealName}>{favorite.meal.name}</Text>
                    <Text style={styles.mealMacros}>
                      {favorite.meal.calories} cal • {favorite.meal.protein}g P • {favorite.meal.carbs}g C • {favorite.meal.fats}g F
                    </Text>
                  </View>
                </View>

                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={styles.logBtn}
                    onPress={() => logMealFromFavorite(favorite)}
                  >
                    <Ionicons name="add-circle" size={18} color={colors.primary} />
                    <Text style={styles.logBtnText}>Log to Diary</Text>
                  </TouchableOpacity>
                  
                  <TouchableOpacity
                    style={styles.removeBtn}
                    onPress={() => removeFavorite(favorite)}
                    disabled={removingId === favorite.id}
                  >
                    {removingId === favorite.id ? (
                      <ActivityIndicator size="small" color={colors.error} />
                    ) : (
                      <Ionicons name="trash-outline" size={18} color={colors.error} />
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
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
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  countText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: 80,
    paddingHorizontal: 40,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
    marginTop: 20,
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  mealCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
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
    backgroundColor: colors.error + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  mealInfo: {
    flex: 1,
    marginLeft: 12,
  },
  mealName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  mealMacros: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  servingSize: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  logBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primary + '15',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
  },
  logBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
  },
  removeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.error + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
