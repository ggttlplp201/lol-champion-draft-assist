# Requirements Document

## Introduction

A League of Legends draft-assist tool that provides intelligent champion pick suggestions during champion select. The system analyzes already picked champions from both teams and recommends champions based on current patch strength, team synergy, and enemy matchups. The tool operates as a standalone application (web app or desktop) and does not interact with the game client.

## Glossary

- **Champion**: A playable character in League of Legends with unique abilities and roles
- **Draft_Phase**: The champion selection period before a match begins
- **Team_Composition**: The combination of champions selected for a team
- **Mastery_Pool**: Champions the user has experience with (manually specified list)
- **Counter_Matchup**: Statistical advantage one champion has over another based on historical match data
- **Synergy**: Win rate improvement when two champions are played together on the same team
- **Patch_Meta**: Current game balance state affecting champion strength based on Riot Games API data
- **Draft_Assist_Tool**: A standalone application that provides champion recommendations without game client interaction
- **Suggestion_Engine**: The system component that calculates and ranks champion recommendations using Riot Games API data

## Requirements

### Requirement 1: Riot Games API Data Integration

**User Story:** As a League of Legends player, I want the tool to use official game data, so that suggestions are based on accurate and up-to-date statistics.

#### Acceptance Criteria

1. WHEN the tool starts, THE Suggestion_Engine SHALL connect to Riot Games Match-V5 API and static data endpoints
2. WHEN calculating patch strength, THE System SHALL use aggregated match data filtered by current patch, role, and rank bucket
3. WHEN computing synergy data, THE System SHALL calculate win rate deltas for champion pairs from historical match data
4. WHEN computing counter matchups, THE System SHALL use head-to-head win rates from role-specific matchup data
5. THE System SHALL cache API responses locally and refresh data every 24 hours

### Requirement 2: User Champion Pool Management

**User Story:** As a player, I want to specify which champions I'm comfortable playing, so that mastery-based suggestions reflect my actual champion pool.

#### Acceptance Criteria

1. WHEN setting up the tool, THE System SHALL allow manual input of user champion pool
2. WHEN displaying mastery-based suggestions, THE System SHALL filter to only champions in the user's specified pool
3. WHEN calculating mastery-based scores, THE System SHALL apply a confidence bonus to champions in the user pool
4. WHEN a user updates their champion pool, THE System SHALL save changes immediately
5. THE System SHALL support importing champion mastery data from Riot Games API if user provides summoner name

### Requirement 3: Draft Context Input

**User Story:** As a player, I want to input current draft state, so that suggestions account for picks, bans, and role constraints.

#### Acceptance Criteria

1. WHEN using the tool, THE System SHALL accept input for the role being picked (single role only for MVP)
2. WHEN champions are selected, THE System SHALL accept ally champion picks (0-4) and enemy champion picks (0-5)
3. WHEN champions are banned, THE System SHALL exclude banned champions from all suggestions
4. WHEN calculating suggestions, THE System SHALL consider blind pick vs counter pick context based on pick order
5. THE System SHALL validate that input champions exist and are available for the specified role

### Requirement 4: Team Composition Analysis

**User Story:** As a player, I want suggestions that complement my team's composition, so that we have a balanced team with proper damage types and team fighting capabilities.

#### Acceptance Criteria

1. WHEN calculating synergy scores, THE System SHALL use win rate deltas for champion pairs from historical match data
2. WHEN analyzing team balance, THE System SHALL consider AP/AD damage distribution and team fighting roles
3. WHEN multiple allies are selected, THE System SHALL calculate average synergy scores with all existing team members
4. WHEN team composition gaps exist, THE System SHALL prioritize champions that fill missing archetypes using coarse composition tags (engage, poke, scaling, etc.)
5. THE System SHALL supplement statistical synergy with basic team composition rules for damage balance

### Requirement 5: Enemy Counter Analysis

**User Story:** As a player, I want suggestions that perform well against enemy picks, so that I can gain strategic advantages in matchups.

#### Acceptance Criteria

1. WHEN enemy champions are selected, THE System SHALL calculate counter scores using role-specific head-to-head win rates
2. WHEN multiple enemies are present, THE System SHALL compute average matchup performance against all enemy champions
3. WHEN counter data is available, THE System SHALL prioritize champions with positive win rate differentials against enemy picks
4. WHEN insufficient matchup data exists, THE System SHALL use general champion archetype advantages as fallback
5. THE System SHALL weight recent patch data more heavily than historical matchup data

### Requirement 6: Patch Meta Integration

**User Story:** As a player, I want suggestions based on current patch strength, so that I pick champions that are viable in the current game state.

#### Acceptance Criteria

1. WHEN calculating meta scores, THE System SHALL use role-specific patch win rates and pick rates from Riot Games API
2. WHEN recent balance changes occur, THE System SHALL weight more recent match data more heavily
3. WHEN patch data is updated, THE System SHALL refresh meta calculations within 24 hours
4. WHEN computing patch strength, THE System SHALL filter data by rank bucket to ensure relevance to user skill level
5. THE System SHALL normalize meta scores to account for champion popularity bias

### Requirement 7: Dual Suggestion Display

**User Story:** As a player, I want to see both champion pool and overall suggestions, so that I can choose between champions I'm comfortable with and optimal picks I might want to learn.

#### Acceptance Criteria

1. WHEN displaying results, THE Draft_Assist_Tool SHALL show two sections: "Top 5 Champion Pool Picks" and "Top 5 Overall Picks"
2. WHEN input changes, THE System SHALL update both suggestion sections immediately
3. WHEN displaying champion pool suggestions, THE System SHALL show only champions from user's specified pool with confidence bonus applied
4. WHEN displaying overall suggestions, THE System SHALL show top champions regardless of user champion pool
5. WHEN a suggestion is selected, THE System SHALL provide 2-4 explanation bullets per recommendation
6. THE Draft_Assist_Tool SHALL clearly label each section and display champion names with recommendation scores

### Requirement 8: Champion Scoring Algorithm

**User Story:** As a developer, I want a mathematical algorithm that calculates champion recommendation scores, so that suggestions are consistent, transparent, and can be fine-tuned.

#### Acceptance Criteria

1. WHEN calculating champion scores, THE Suggestion_Engine SHALL use weighted sum: Score = (Meta_Score × 0.4) + (Synergy_Score × 0.3) + (Counter_Score × 0.3)
2. WHEN computing meta scores, THE System SHALL use role-specific patch win rates normalized to 0-100 scale
3. WHEN computing synergy scores, THE System SHALL use average win rate deltas with allied champions normalized to 0-100 scale
4. WHEN computing counter scores, THE System SHALL use average matchup win rates against enemy champions normalized to 0-100 scale
5. WHEN calculating champion pool suggestions, THE System SHALL apply a +15 confidence bonus to final scores for champions in user pool
6. THE System SHALL provide score breakdowns for debugging and transparency

### Requirement 9: Explainable Recommendations

**User Story:** As a player, I want to understand why champions are recommended, so that I can make informed decisions and learn from the suggestions.

#### Acceptance Criteria

1. WHEN displaying each recommendation, THE System SHALL provide 2-4 explanation bullets using deterministic rules
2. WHEN a champion has high meta score, THE System SHALL include explanation: "Strong pick in the current patch"
3. WHEN a champion has high synergy score, THE System SHALL include explanation: "Synergizes well with [ally champion name]"
4. WHEN a champion has high counter score, THE System SHALL include explanation: "Performs well against [enemy champion name]"
5. WHEN a champion balances team composition, THE System SHALL include explanation: "Balances team damage profile" or "Provides missing [archetype]"
6. THE System SHALL generate explanations based on the highest contributing score components
### Requirement 10: Data Persistence and Settings

**User Story:** As a player, I want my champion pool and preferences saved, so that the tool remembers my settings between sessions.

#### Acceptance Criteria

1. WHEN the application closes, THE System SHALL save user champion pool and preference settings to local storage
2. WHEN the application starts, THE System SHALL load previous session data automatically
3. WHEN champion pool is modified, THE System SHALL persist changes immediately
4. WHEN API data is cached, THE System SHALL store it locally with timestamps for refresh management
5. THE System SHALL provide export/import functionality for user champion pool data