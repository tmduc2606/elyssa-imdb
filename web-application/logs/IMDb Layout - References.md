****IMDb Platform Data Structure & UI Layout Summary****  
__Designed for AI Agents (Text-Only Parsing Context)__

The IMDb website is structured as a hierarchical, entity-driven media database. Below is the comprehensive structural layout detailing the navigation, entity relationships, and data fields available across the interface.

### 1\. Global Navigation & Header (Persistent Element)

-   ****Branding & Search:****
-   -   Logo (Top left).
    -   ****Search Bar:**** Centralized element with a dropdown ("All") to filter search by Movies, TV Shows, Celebs, etc., and a magnifying glass trigger.
-   ****User & Utility Bar (Top right):****
-   -   ****IMDbPro:**** Link to the professional subscription service.
    -   ****Watchlist:**** User-specific tracking list (requires sign-in to populate).
    -   ****Sign In:**** Authentication entry point.
    -   ****Language Selector:**** Dropdown (e.g., "EN").

### 2\. Entity Detail Page (Movie / TV Show)

__This layout applies to entity pages (e.g., the example page for "Spider-Man: Brand New Day").__

****A. Hero Section (Top Page)****

-   ****Title Header:**** Title, Year, PG-13 Rating, Runtime, MPAA rating.
-   ****Primary Media:**** Large hero image/trailer player with controls (Play trailer, runtime, like/dislike counts).
-   ****Action Buttons:****
-   -   "Add to Watchlist" (Yellow button with + icon, includes count of users who added it).
    -   "Mark as watched" (Toggle button).
-   ****Genre Tags:**** Interactive filter pills (e.g., Marvel, Superhero, Urban Adventure, Action, Adventure, Sci-Fi).
-   ****Core Credits (Brief):**** Key personnel (Director, Writers, Stars) displayed with chevron arrows leading to full cast/crew pages.
-   ****Ratings Box (Top Right):****
-   -   IMDb Rating (out of 10, with vote count, e.g., 8.1/10 - 177k).
    -   Your Rating prompt (Star rating widget).
    -   Popularity rank (e.g., #1 with an up/down trend arrow).
    -   Links to User reviews (2.1K) and Critic reviews (243).
    -   Metascore (if available).

****B. Content & Metadata Tiles (Below Hero)****

-   ****Storyline:**** A long-form text summary of the plot. Includes tabs for "Plot summary" vs "Plot synopsis".
-   ****Taglines:**** A short, punchy descriptive line.
-   ****Genres & Keywords:**** Core genres (Action, Adventure, Sci-Fi) and extensive keyword/tag buttons (Marvel, the punisher character, shared universe, etc., plus a "333 more" expander).
-   ****Motion Picture Rating:**** Specific rating notes (e.g., "Rated PG-13 for sequences of action/violence and some language.").
-   ****Parents Guide:**** Link to a dedicated page detailing adult content.

****C. Top Cast & Crew (Card Grid)****

-   A horizontal scrolling card grid featuring circular profile images of actors.
-   ****Data per card:**** Actor Name, Character Name played in this entity.
-   ****Header:**** Includes a chevron link to view the full "99+" cast list.

****D. User Interaction & Community Section****

-   ****User Reviews (Section):****
-   -   Aggregate score bar chart (1-10 star distribution).
    -   Summary section (often gated behind a "Sign in to see this summary and all user reviews" overlay prompt).
    -   "Featured reviews" cards (User avatar, rating score, title of review, snippet of text, upvote/downvote buttons).
-   ****User Polls:**** Related polls from IMDb users (e.g., "Most Anticipated Movie of 2024", "Which 2026 Movie Will Exceed Your Expectations?").
-   ****User Lists:**** Community-generated lists (e.g., "Interesting", "Films I Have Seen in 2026") displayed as horizontal cards with the number of titles.

****E. Media Galleries****

-   ****Videos:**** Grid of thumbnail cards containing the trailer length, play button, title, views, and like/dislike counts.
-   ****Photos:**** Thumbnail gallery with an "Add photo" contribution button.

****F. Did You Know (Trivia Section)****

-   Accordion-style list with sections for:
-   -   ****Trivia:**** Dedications, behind-the-scenes facts.
    -   ****Goofs:**** Continuity errors, factual errors.
    -   ****Quotes:**** Dialog snippets from the movie.
    -   ****Crazy Credits:**** Easter eggs during the credits.
    -   ****Alternate Versions:**** Regional cuts/censorship differences (e.g., CBFC cuts in India).
    -   ****Connections:**** Cross-media links (e.g., featured in another movie).
    -   ****Soundtracks:**** List of songs with performers/writers.

****G. Technical & Business Details (Accordion)****

-   ****Details:**** Release date (month, day, year), Countries of origin, Official sites (Marvel, Sony), Language, Also known as (alternate titles), Filming locations, Production companies.
-   ****Box Office:**** Budget (estimated), Gross US & Canada, Opening weekend (with date), Gross Worldwide.
-   ****Tech Specs:**** Runtime, Color format.

****H. Recommendation Engines (Carousels)****

-   ****More Like This:**** Horizontal carousel of movie posters with ratings for similar titles.
-   ****Top Picks:**** Personalized carousel based on user history (requires sign-in, shows "Sign in" CTA if not logged in).
-   ****Related Interests:**** Categorized carousels (e.g., "Marvel", "Superhero", "Urban Adventure").
-   ****Contribute to this page:**** Section with links to Suggest an edit, Learn more about contributing, and a prominent yellow "Edit page" button.

### 3\. Homepage Structure (Landing Pages)

-   ****Hero Carousel (Top):**** Highlighted featured media (films/TV shows) with a large play button, title, and "Watch Trailer" call to action.
-   ****Up Next:**** Sidebar list of "What to watch" / Featured trailers.
-   ****Top 10 on IMDb this week:**** Numbered list (1-10) of movies and shows, showing the poster art, title, year, rating, and a plot snippet.
-   ****Fan Favorites:**** Horizontal carousel of "This week's top TV and movies".
-   ****Trending People:**** Circular avatar carousel of rising stars/celebs. Includes a specific rank number and a "Top Rising" or "By Ranking" metric (e.g., "+286,401").
-   ****Explore what's streaming:**** Filter by streaming service (e.g., Prime Video) displaying rows of content with their IMDb ratings.
-   ****Coming soon to theaters:**** Horizontal carousel of upcoming release trailers, with release dates (AUG 14, AUG 28, etc.).
-   ****Born today:**** Circular avatar list of celebrities born on the current date, showing their names and age.

### 4\. Main Menu Overlay (Hamburger Sidebar)

-   ****Movies:**** Release calendar, Top 250 movies, Most popular movies, Browse movies by genre, Top box office, Showtimes & tickets, Movie news, India movie spotlight.
-   ****TV shows:**** What's on TV & streaming, Top 250 TV shows, Most popular TV shows, Browse TV shows by genre, TV news.
-   ****Watch:**** What to watch, Latest trailers, IMDb Originals, IMDb Picks, IMDb Spotlight, Family entertainment guide, IMDb Podcasts.
-   ****Awards & events:**** Oscars, Primetime Emmys, San Diego Comic-Con, Summer Watch Guide, Most Anticipated This Month, IMDb Labs, STARmeter Awards, Awards Central, Festival Central, All events.
-   ****Celebs:**** Born today, Trending people, Celebrity news.
-   ****Community:**** Help center, Contributor zone, Polls.

### 5\. Global Footer (Persistent Element)

-   ****Call to Action:**** "Sign in for more access" (Yellow pill button).
-   ****Social & App:****
-   -   Follow IMDb on socials (TikTok, Instagram, X, YouTube, Facebook).
    -   Get the IMDb app (Android/iOS, includes a QR code).
-   ****Legal & Corporate Menu:**** Help, Site Index, IMDbPro, Box Office Mojo, License IMDb Data, Press Room, Advertising, Jobs, Conditions of Use, Privacy Policy, Your Ads Privacy Choices.
-   ****Branding:**** "An Amazon company" tag and copyright text (© 1990-2026 by [IMDb.com](https://imdb.com/), Inc.).