# GenMedia Creative Studio: Administrator FAQ

This document provides guidance for administrators on managing user access, roles, and monitoring system activity.

## 1. Access Control & Authorization

*   **Q: How does the application decide who can enter?**
    *   **A:** The app uses a two-tier gate check. First, it looks for the user's email in the Firestore `users` collection. If not found, it checks if the user's email domain matches any domain listed in the `DOMAIN_ALLOWLIST` environment variable.
*   **Q: What happens when an unauthorized user tries to log in?**
    *   **A:** They are immediately redirected to a terminal `/forbidden` page. Their attempt is also recorded in the `unauthorized_access_logs` Firestore collection for your review.
*   **Q: How do I grant access to someone from an external domain?**
    *   **A:** Go to the **Admin Dashboard** within the app, click the **"Add User"** button in the **Users** tab, and enter their email address. This overrides any domain-level restrictions.

## 2. Roles & Permissions

*   **Q: What are the available roles?**
    *   **A:** 
        *   `creator` (Default): Full access to all generative media tools.
        *   `builder`: Reserved for users who will eventually manage configurations and presets.
        *   `admin`: Full access to the app plus the **Admin Dashboard** for user and log management.
*   **Q: How do I change a user's role?**
    *   **A:** In the **Admin Dashboard**, click on any user's row in the **Users** tab. This opens the **Edit User Profile** dialog where you can select a new role and save changes.
*   **Q: How can I see who is currently an Admin?**
    *   **A:** In the **Admin Dashboard**, the "Users" tab displays the role next to every authorized email address. You can also see your own role in parentheses next to your username on the **Configuration** page.

## 3. User Management

*   **Q: What is the tabbed interface in the Dashboard?**
    *   **A:** The Dashboard is split into two tabs: 
        1. **Users:** For managing active allowlisted users and their roles.
        2. **Unauthorized Logs:** For viewing a chronological list of blocked login attempts.
*   **Q: How does the "Last Signed In" time work?**
    *   **A:** The app records a UTC timestamp every time an authorized user successfully completes the login handshake. This helps you track platform adoption and activity.
*   **Q: Can I revoke access instantly?**
    *   **A:** Yes. Deleting a user's document from the **Users** tab (via the trash icon) will block their access on their next page navigation or session refresh.

## 4. System Resilience (Avatars & Media)

*   **Q: Why does the Admin Dashboard show custom avatars instead of just Google photos?**
    *   **A:** To prevent "broken image" icons caused by Google's rate limits (429 errors), the app "mirrors" every user's profile picture to our own GCS bucket. The Admin Dashboard prioritizes these mirrored versions for a faster, more reliable UI.
*   **Q: What if a user's avatar is still broken?**
    *   **A:** The app includes a safety fallback. If both the Google URL and the mirrored GCS version fail, a generic "Anonymous User" icon is displayed automatically.

## 5. Technical Maintenance

*   **Q: Where is the data stored?**
    *   **A:** All user metadata and access logs are stored in Firestore. Mirrored profile pictures are stored in the `GENMEDIA_BUCKET` under the `/avatars` prefix.
*   **Q: Do I need to clear any caches when I update the Allowlist?**
    *   **A:** No. We have disabled server-side caching for authorization checks to ensure that access changes (grants or revocations) take effect immediately.
