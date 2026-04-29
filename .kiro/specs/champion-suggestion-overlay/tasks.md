# Implementation Plan: Champion Draft Assist Tool

## Overview

This implementation plan focuses on building an MVP champion draft assist tool for mid lane recommendations. The approach prioritizes core functionality: data aggregation from Riot Games API, mathematical scoring algorithms, and a simple interface for user interaction.

## Tasks

- [x] 1. Set up project structure and core interfaces
  - Create Python project with virtual environment
  - Define core data models (Champion, DraftState, ChampionRecommendation)
  - Set up basic project structure with modules for data, scoring, and interface
  - Install required dependencies (requests, click, pytest, hypothesis)
  - _Requirements: 1.1, 2.1_

- [x] 2. Implement Riot Games API integration
  - [x] 2.1 Create API client for Riot Games endpoints
    - Implement connection to Match-V5 API and Data Dragon
    - Add API key management and basic error handling
    - _Requirements: 1.1_

  - [ ]* 2.2 Write property test for API data filtering
    - **Property 1: API Data Filtering Consistency**
    - **Validates: Requirements 1.2**

  - [x] 2.3 Implement champion data fetching
    - Fetch mid lane champion list from Data Dragon
    - Parse champion metadata and roles
    - _Requirements: 1.1_

  - [ ]* 2.4 Write unit tests for API client
    - Test API connection and error handling
    - Test champion data parsing
    - _Requirements: 1.1_

- [x] 3. Implement data aggregation and statistics calculation
  - [x] 3.1 Create match data aggregation system
    - Filter matches by patch and mid lane role
    - Calculate individual champion win rates
    - _Requirements: 1.2_

  - [x] 3.2 Implement synergy calculation (duo delta method)
    - Calculate expected vs actual combined win rates
    - Implement win rate delta calculation for champion pairs
    - _Requirements: 1.3, 4.1_

  - [ ]* 3.3 Write property test for synergy calculation
    - **Property 2: Synergy Score Calculation Accuracy**
    - **Validates: Requirements 1.3, 4.1, 8.3**

  - [x] 3.4 Implement counter calculation (head-to-head method)
    - Calculate head-to-head win rates for mid lane matchups
    - Normalize counter scores to 0-100 scale
    - _Requirements: 1.4, 5.1_

  - [ ]* 3.5 Write property test for counter calculation
    - **Property 3: Counter Score Calculation Accuracy**
    - **Validates: Requirements 1.4, 5.1, 8.4**

- [x] 4. Checkpoint - Ensure data processing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement champion scoring algorithm
  - [x] 5.1 Create meta score calculator
    - Calculate patch-specific win rates for mid lane champions
    - Normalize meta scores to 0-100 scale
    - _Requirements: 6.1, 8.2_

  - [x] 5.2 Implement weighted scoring system
    - Combine meta (40%), synergy (30%), counter (30%) scores
    - Apply configurable confidence bonus for champion pool
    - _Requirements: 8.1_

  - [x] 5.3 Write property test for weighted scoring
    - **Property 5: Weighted Score Calculation**
    - **Validates: Requirements 8.1**

  - [ ]* 5.4 Write property test for confidence bonus
    - **Property 6: Configurable Confidence Bonus Application**
    - **Validates: Requirements 2.3, 8.5**

- [x] 6. Implement suggestion engine
  - [x] 6.1 Create recommendation generator
    - Generate champion pool and overall recommendations
    - Exclude banned champions from all suggestions
    - _Requirements: 2.2, 3.3, 7.3, 7.4_

  - [ ]* 6.2 Write property test for banned champion exclusion
    - **Property 4: Banned Champion Exclusion**
    - **Validates: Requirements 3.3**

  - [x] 6.3 Implement explanation generation
    - Generate deterministic explanations based on score components
    - Include meta, synergy, and counter explanations
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 6.4 Write property test for explanation determinism
    - **Property 7: Explanation Generation Determinism**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

- [x] 7. Create CLI interface
  - [x] 7.1 Implement command-line interface using Click
    - Accept draft state input (allies, enemies, banned champions)
    - Display champion pool and overall recommendations
    - Show explanations and score breakdowns
    - _Requirements: 7.1, 7.6_

  - [ ]* 7.2 Write unit tests for CLI interface
    - Test input validation and output formatting
    - Test recommendation display logic
    - _Requirements: 7.1, 7.6_

- [x] 8. Integration and testing
  - [x] 8.1 Create end-to-end integration tests
    - Test complete workflow from API data to recommendations
    - Verify recommendation accuracy with known scenarios
    - _Requirements: All_

  - [x] 8.2 Add basic caching for API responses
    - Cache champion data and match statistics locally
    - Implement simple TTL-based cache invalidation
    - _Requirements: 1.5_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis library
- Unit tests validate specific examples and edge cases
- Focus on mid lane only for MVP scope