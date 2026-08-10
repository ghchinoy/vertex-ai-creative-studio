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

package common

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestParseGCSBucketAndPrefix(t *testing.T) {
	tests := []struct {
		name       string
		uri        string
		wantBucket string
		wantPrefix string
	}{
		{"bucket only", "my-bucket", "my-bucket", ""},
		{"bucket only with gs scheme", "gs://my-bucket", "my-bucket", ""},
		{"bucket with trailing slash", "gs://my-bucket/", "my-bucket", ""},
		{"bucket and prefix", "gs://my-bucket/prefix", "my-bucket", "prefix/"},
		{"bucket and prefix trailing slash preserved", "gs://my-bucket/prefix/", "my-bucket", "prefix/"},
		{"bucket and nested prefix", "gs://my-bucket/a/b/c", "my-bucket", "a/b/c/"},
		{"bucket and nested prefix trailing slash", "gs://my-bucket/a/b/c/", "my-bucket", "a/b/c/"},
		{"no gs scheme with prefix", "my-bucket/spike_a", "my-bucket", "spike_a/"},
		{"leading slash stripped", "/my-bucket/prefix", "my-bucket", "prefix/"},
		{"gs scheme leading slash", "gs:///my-bucket/prefix", "my-bucket", "prefix/"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			gotBucket, gotPrefix := ParseGCSBucketAndPrefix(tc.uri)
			if gotBucket != tc.wantBucket {
				t.Errorf("ParseGCSBucketAndPrefix(%q) bucket = %q, want %q", tc.uri, gotBucket, tc.wantBucket)
			}
			if gotPrefix != tc.wantPrefix {
				t.Errorf("ParseGCSBucketAndPrefix(%q) prefix = %q, want %q", tc.uri, gotPrefix, tc.wantPrefix)
			}
		})
	}
}

func TestSignedURLExpiryFromEnv(t *testing.T) {
	const def = 24 * time.Hour  // default validity
	const max = 168 * time.Hour // V4 ceiling
	const envVar = "TEST_SIGNED_URL_EXPIRY_HOURS"
	tests := []struct {
		name   string
		env    string // value to set; "" means unset/empty
		setEnv bool
		want   time.Duration
	}{
		{"unset defaults to 24h", "", false, def},
		{"empty defaults to 24h", "", true, def},
		{"explicit 24h", "24", true, 24 * time.Hour},
		{"1h", "1", true, 1 * time.Hour},
		{"exactly 168 stays 168", "168", true, max},
		{"over 168 clamps to 168", "200", true, max},
		{"way over clamps to 168", "100000", true, max},
		{"zero disables", "0", true, 0},
		{"negative -> default", "-5", true, def},
		{"non-numeric -> default", "notanumber", true, def},
		{"float -> default (Atoi fails)", "24.5", true, def},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			// t.Setenv cannot truly unset; empty string is treated as unset.
			t.Setenv(envVar, tc.env)
			if got := SignedURLExpiryFromEnv(envVar); got != tc.want {
				t.Errorf("SignedURLExpiryFromEnv(%q) with env=%q = %v, want %v", envVar, tc.env, got, tc.want)
			}
		})
	}
}

// TestPersistMediaOutputsLocalOnly verifies the local-write path of
// PersistMediaOutputs without touching GCS (gcsBucketURI empty).
func TestPersistMediaOutputsLocalOnly(t *testing.T) {
	dir := t.TempDir()
	art := MediaArtifact{
		Data:     []byte("hello-mp4-bytes"),
		MimeType: "video/mp4",
		FileName: "omni_20260101_0.mp4",
	}

	got, err := PersistMediaOutputs(context.Background(), art, dir, "", 0)
	if err != nil {
		t.Fatalf("PersistMediaOutputs returned fatal error: %v", err)
	}
	wantPath := filepath.Join(dir, art.FileName)
	if got.LocalPath != wantPath {
		t.Errorf("LocalPath = %q, want %q", got.LocalPath, wantPath)
	}
	if got.GCSURI != "" || got.SignedURL != "" || got.GCSError != nil {
		t.Errorf("expected no GCS fields, got %+v", got)
	}
	data, err := os.ReadFile(wantPath)
	if err != nil {
		t.Fatalf("reading persisted file: %v", err)
	}
	if string(data) != string(art.Data) {
		t.Errorf("persisted bytes = %q, want %q", data, art.Data)
	}
}

// TestPersistMediaOutputsNoDestinations verifies that with neither a local dir
// nor a GCS URI the call is a no-op (no error, empty result).
func TestPersistMediaOutputsNoDestinations(t *testing.T) {
	got, err := PersistMediaOutputs(context.Background(), MediaArtifact{Data: []byte("x"), FileName: "f.mp4"}, "", "", 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.LocalPath != "" || got.GCSURI != "" || got.SignedURL != "" || got.GCSError != nil {
		t.Errorf("expected empty result, got %+v", got)
	}
}
