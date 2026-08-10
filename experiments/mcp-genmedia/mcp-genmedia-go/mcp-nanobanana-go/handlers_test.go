// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"testing"
	"time"

	common "github.com/GoogleCloudPlatform/vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-common"
)

func TestExtForMimeType(t *testing.T) {
	tests := []struct {
		mimeType string
		want     string
	}{
		{"image/jpeg", ".jpg"},
		{"image/webp", ".webp"},
		{"image/gif", ".gif"},
		{"image/png", ".png"},
		{"application/octet-stream", ".png"}, // unknown -> default png
		{"", ".png"},                         // empty -> default png
		{"image/JPEG", ".png"},               // case-sensitive: not matched -> default png
	}
	for _, tc := range tests {
		t.Run(tc.mimeType, func(t *testing.T) {
			if got := extForMimeType(tc.mimeType); got != tc.want {
				t.Errorf("extForMimeType(%q) = %q, want %q", tc.mimeType, got, tc.want)
			}
		})
	}
}

// TestSignedURLExpiryWiring guards the nanobanana-specific env var name that is
// read through the shared common.SignedURLExpiryFromEnv helper. The exhaustive
// clamp/default/disable behavior is covered by common's own tests; this only
// asserts the wiring (correct env var, values honored) after the extraction.
func TestSignedURLExpiryWiring(t *testing.T) {
	const envVar = "NANOBANANA_SIGNED_URL_EXPIRY_HOURS"

	t.Run("default when unset", func(t *testing.T) {
		t.Setenv(envVar, "")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 24*time.Hour {
			t.Errorf("got %v, want 24h", got)
		}
	})
	t.Run("explicit value honored", func(t *testing.T) {
		t.Setenv(envVar, "6")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 6*time.Hour {
			t.Errorf("got %v, want 6h", got)
		}
	})
	t.Run("zero disables", func(t *testing.T) {
		t.Setenv(envVar, "0")
		if got := common.SignedURLExpiryFromEnv(envVar); got != 0 {
			t.Errorf("got %v, want 0", got)
		}
	})
}
