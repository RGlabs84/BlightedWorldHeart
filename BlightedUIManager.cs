using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;

namespace BlightedHeart
{
    public class BlightedUIManager : MonoBehaviour
    {
        private static BlightedUIManager _instance;
        public static BlightedUIManager Instance => _instance;

        private GameObject _uiRoot;
        private BlightedWorldHeartAI _activeHeart;
        
        // Track these so UI can persist after the heart is destroyed
        private Character _trackedSubBoss1;
        private Character _trackedSubBoss2;
        private Vector3 _heartPosition;

        // UI Elements
        private RectTransform _mainBossBar;
        private Image _mainBossFill;
        private Text _mainBossName;

        private RectTransform _subBoss1Bar;
        private Image _subBoss1Fill;
        private Text _subBoss1Name;

        private RectTransform _subBoss2Bar;
        private Image _subBoss2Fill;
        private Text _subBoss2Name;

        private Font _valheimFont;

        public void Awake()
        {
            _instance = this;
        }

        public void RegisterHeart(BlightedWorldHeartAI heart)
        {
            _activeHeart = heart;
            if (_activeHeart != null)
            {
                _heartPosition = _activeHeart.transform.position;
            }
            if (_uiRoot == null && Hud.instance != null)
            {
                CreateUI();
            }
        }

        public void UnregisterHeart(BlightedWorldHeartAI heart)
        {
            if (_activeHeart == heart)
            {
                _activeHeart = null;
                // DO NOT disable UI here — let LateUpdate decide based on subbosses
            }
        }

        private void CreateUI()
        {
            if (Hud.instance == null || Hud.instance.m_rootObject == null) return;

            // Try to find Valheim's font from an existing UI element
            var existingText = Hud.instance.m_rootObject.GetComponentInChildren<Text>(true);
            if (existingText != null) _valheimFont = existingText.font;

            _uiRoot = new GameObject("BlightedCustomBossUI");
            _uiRoot.transform.SetParent(Hud.instance.m_rootObject.transform, false);
            
            var rt = _uiRoot.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.5f, 1f);
            rt.anchorMax = new Vector2(0.5f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.anchoredPosition = new Vector2(0, -50f); // 50 pixels from top

            // Main Boss Bar (Center)
            CreateHealthBar("MainBossBar", _uiRoot.transform, new Vector2(0, 0), new Vector2(600, 30), out _mainBossBar, out _mainBossFill, out _mainBossName);
            
            // Sub Boss 1 (Left, below main)
            CreateHealthBar("SubBoss1Bar", _uiRoot.transform, new Vector2(-200, -50), new Vector2(250, 20), out _subBoss1Bar, out _subBoss1Fill, out _subBoss1Name);
            
            // Sub Boss 2 (Right, below main)
            CreateHealthBar("SubBoss2Bar", _uiRoot.transform, new Vector2(200, -50), new Vector2(250, 20), out _subBoss2Bar, out _subBoss2Fill, out _subBoss2Name);

            _uiRoot.SetActive(false);
        }

        private void CreateHealthBar(string name, Transform parent, Vector2 anchoredPos, Vector2 size, out RectTransform rootRt, out Image fill, out Text nameText)
        {
            GameObject barObj = new GameObject(name);
            barObj.transform.SetParent(parent, false);
            rootRt = barObj.AddComponent<RectTransform>();
            rootRt.anchorMin = new Vector2(0.5f, 1f);
            rootRt.anchorMax = new Vector2(0.5f, 1f);
            rootRt.pivot = new Vector2(0.5f, 1f);
            rootRt.anchoredPosition = anchoredPos;
            rootRt.sizeDelta = size;

            // Gold Trim Background
            GameObject trimObj = new GameObject("Trim");
            trimObj.transform.SetParent(barObj.transform, false);
            var trimRt = trimObj.AddComponent<RectTransform>();
            trimRt.anchorMin = Vector2.zero;
            trimRt.anchorMax = Vector2.one;
            // Expand slightly outside the main box by 2 pixels on all sides
            trimRt.offsetMin = new Vector2(-2, -2);
            trimRt.offsetMax = new Vector2(2, 2);
            var trimImg = trimObj.AddComponent<Image>();
            trimImg.color = new Color(1f, 0.84f, 0f, 1f); // Gold!

            // Black Background
            GameObject bkgObj = new GameObject("Bkg");
            bkgObj.transform.SetParent(barObj.transform, false);
            var bkgRt = bkgObj.AddComponent<RectTransform>();
            bkgRt.anchorMin = Vector2.zero;
            bkgRt.anchorMax = Vector2.one;
            bkgRt.sizeDelta = Vector2.zero;
            var bkgImg = bkgObj.AddComponent<Image>();
            bkgImg.color = new Color(0, 0, 0, 0.9f); // Solid dark

            // Fill
            GameObject fillObj = new GameObject("Fill");
            fillObj.transform.SetParent(barObj.transform, false);
            var fillRt = fillObj.AddComponent<RectTransform>();
            fillRt.anchorMin = new Vector2(0, 0);
            fillRt.anchorMax = new Vector2(1, 1);
            fillRt.sizeDelta = Vector2.zero;
            fillRt.pivot = new Vector2(0, 0.5f); // Scale from left
            fill = fillObj.AddComponent<Image>();
            fill.color = Color.magenta;

            GameObject textObj = new GameObject("NameText");
            textObj.transform.SetParent(barObj.transform, false);
            var textRt = textObj.AddComponent<RectTransform>();
            textRt.anchorMin = new Vector2(0.5f, 0.5f);
            textRt.anchorMax = new Vector2(0.5f, 0.5f);
            textRt.pivot = new Vector2(0.5f, 0.5f);
            textRt.anchoredPosition = new Vector2(0, 0); // Center in the bar
            textRt.sizeDelta = new Vector2(500, 30);
            nameText = textObj.AddComponent<Text>();
            nameText.alignment = TextAnchor.MiddleCenter;
            nameText.color = Color.white;
            nameText.fontSize = 20; // Ensure a readable font size
            
            if (_valheimFont != null) 
            {
                nameText.font = _valheimFont;
            }
            else
            {
                // Fallback if Valheim font couldn't be loaded dynamically
                nameText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            }
            
            // Add slight shadow to text for readability
            var shadow = textObj.AddComponent<Shadow>();
            shadow.effectColor = Color.black;
            shadow.effectDistance = new Vector2(1, -1);
        }

        public void LateUpdate()
        {
            if (Hud.instance == null) return;
            
            // Update tracking if active heart is alive
            if (_activeHeart != null && _activeHeart.m_health > 0)
            {
                _heartPosition = _activeHeart.transform.position;
                if (_activeHeart.m_subBoss1 != null) _trackedSubBoss1 = _activeHeart.m_subBoss1;
                if (_activeHeart.m_subBoss2 != null) _trackedSubBoss2 = _activeHeart.m_subBoss2;
            }
            
            bool heartAlive = _activeHeart != null && _activeHeart.m_health > 0;
            bool sb1Alive = _trackedSubBoss1 != null && !_trackedSubBoss1.IsDead();
            bool sb2Alive = _trackedSubBoss2 != null && !_trackedSubBoss2.IsDead();

            // If everything is dead, hide UI
            if (!heartAlive && !sb1Alive && !sb2Alive)
            {
                if (_uiRoot != null && _uiRoot.activeSelf) _uiRoot.SetActive(false);
                return;
            }

            // Check distance
            if (Player.m_localPlayer != null)
            {
                float dist = Vector3.Distance(Player.m_localPlayer.transform.position, _heartPosition);
                if (dist > 100f) // Show boss bar if within 100 meters
                {
                    if (_uiRoot != null && _uiRoot.activeSelf) _uiRoot.SetActive(false);
                    return;
                }
            }

            if (_uiRoot == null) CreateUI();
            if (_uiRoot == null) return; // Still failed to create

            if (!_uiRoot.activeSelf) _uiRoot.SetActive(true);

            UpdateBars(heartAlive, sb1Alive, sb2Alive);
        }

        private void UpdateBars(bool heartAlive, bool sb1Alive, bool sb2Alive)
        {
            if (heartAlive)
            {
                _mainBossBar.gameObject.SetActive(true);
                float mainHealth = _activeHeart.m_health;
                float mainMaxHealth = _activeHeart.m_maxHealth;
                _mainBossFill.color = GetBiomeColor(_activeHeart.CurrentBiome);
                _mainBossName.text = "Blighted World Heart";
                UpdateFill(_mainBossFill, mainHealth, mainMaxHealth);
            }
            else
            {
                _mainBossBar.gameObject.SetActive(false);
            }

            // Reset subboss layout
            float baseYOffset = heartAlive ? -50f : 0f; // Move up if heart is dead

            if (sb1Alive)
            {
                _subBoss1Bar.gameObject.SetActive(true);
                _subBoss1Name.text = GetLocalizedBlightedName(_trackedSubBoss1.m_name);
                _subBoss1Fill.color = new Color(0.2f, 0.6f, 1f, 1f); // Blighted Blue
                UpdateFill(_subBoss1Fill, _trackedSubBoss1.GetHealth(), _trackedSubBoss1.GetMaxHealth());
            }
            else
            {
                _subBoss1Bar.gameObject.SetActive(false);
            }

            if (sb2Alive)
            {
                _subBoss2Bar.gameObject.SetActive(true);
                _subBoss2Name.text = GetLocalizedBlightedName(_trackedSubBoss2.m_name);
                _subBoss2Fill.color = new Color(0.2f, 0.6f, 1f, 1f); // Blighted Blue
                UpdateFill(_subBoss2Fill, _trackedSubBoss2.GetHealth(), _trackedSubBoss2.GetMaxHealth());
            }
            else
            {
                _subBoss2Bar.gameObject.SetActive(false);
            }

            // Dynamic Layout Adjustment
            if (sb1Alive && sb2Alive)
            {
                // Both alive: split side by side
                _subBoss1Bar.sizeDelta = new Vector2(250, 20);
                _subBoss1Bar.anchoredPosition = new Vector2(-200, baseYOffset);
                _subBoss1Name.fontSize = 20;

                _subBoss2Bar.sizeDelta = new Vector2(250, 20);
                _subBoss2Bar.anchoredPosition = new Vector2(200, baseYOffset);
                _subBoss2Name.fontSize = 20;
            }
            else if (sb1Alive && !sb2Alive && !heartAlive)
            {
                // Only SB1 alive and heart is dead: expand to full width and center
                _subBoss1Bar.sizeDelta = new Vector2(600, 30);
                _subBoss1Bar.anchoredPosition = new Vector2(0, 0); // Center
                _subBoss1Name.fontSize = 24;
            }
            else if (!sb1Alive && sb2Alive && !heartAlive)
            {
                // Only SB2 alive and heart is dead: expand to full width and center
                _subBoss2Bar.sizeDelta = new Vector2(600, 30);
                _subBoss2Bar.anchoredPosition = new Vector2(0, 0); // Center
                _subBoss2Name.fontSize = 24;
            }
            else if (sb1Alive && !sb2Alive && heartAlive)
            {
                // Only SB1 alive but heart is alive: keep normal size and move to center under heart
                _subBoss1Bar.sizeDelta = new Vector2(250, 20);
                _subBoss1Bar.anchoredPosition = new Vector2(0, baseYOffset);
                _subBoss1Name.fontSize = 20;
            }
            else if (!sb1Alive && sb2Alive && heartAlive)
            {
                // Only SB2 alive but heart is alive: keep normal size and move to center under heart
                _subBoss2Bar.sizeDelta = new Vector2(250, 20);
                _subBoss2Bar.anchoredPosition = new Vector2(0, baseYOffset);
                _subBoss2Name.fontSize = 20;
            }
        }

        private void UpdateFill(Image fill, float current, float max)
        {
            float pct = Mathf.Clamp01(max > 0 ? current / max : 0);
            fill.transform.localScale = new Vector3(pct, 1, 1);
        }

        private string GetLocalizedBlightedName(string rawName)
        {
            if (string.IsNullOrEmpty(rawName)) return "Blighted Unknown";
            if (rawName.StartsWith("Blighted")) return rawName; // Fallback
            string localized = Localization.instance.Localize(rawName);
            return $"Blighted {localized}";
        }

        private Color GetBiomeColor(Heightmap.Biome biome)
        {
            switch (biome)
            {
                case Heightmap.Biome.Meadows: return new Color(0.2f, 0.8f, 0.2f);
                case Heightmap.Biome.BlackForest: return new Color(0.5f, 0.1f, 0.8f);
                case Heightmap.Biome.Swamp: return new Color(0.4f, 0.3f, 0.1f);
                case Heightmap.Biome.Mountain: return new Color(0.8f, 0.9f, 1.0f);
                case Heightmap.Biome.Plains: return new Color(0.9f, 0.7f, 0.2f);
                case Heightmap.Biome.Mistlands: return new Color(0.3f, 0.1f, 0.5f);
                case Heightmap.Biome.AshLands: return new Color(1.0f, 0.2f, 0.0f);
                case Heightmap.Biome.DeepNorth: return new Color(0.9f, 0.9f, 1.0f);
                default: return Color.white;
            }
        }
    }
}
