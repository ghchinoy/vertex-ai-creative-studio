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

// Package common provides shared utilities for the MCP Genmedia servers.

package common

import (
	"context"
	"errors"
	"fmt"
	"log"

	"cloud.google.com/go/storage"
)

// GCS has no atomic rename. For the "API-controls-GCS" servers (imagen/veo) the
// model writes objects into a prefix and names them itself (sample_0.png, ...).
// To honor a client-supplied output_filename those objects are copied to the
// desired name and the originals deleted. The exact copy-fatal / delete-nonfatal
// contract is design #842 §4d.

// copyGCSObjectFn, deleteGCSObjectFn and gcsObjectExistsFn indirect over the
// real server-side GCS copy, delete and existence-check so the copy-fatal /
// delete-nonfatal / collision branches of the rename helpers are unit-testable
// without a live bucket or credentials. They default to the real
// implementations (production behavior is unchanged) and are only reassigned by
// tests, which restore them afterwards — mirroring the uploadToGCSFn /
// generateV4SignedURLFn indirection in media_output.go.
var (
	copyGCSObjectFn   = copyGCSObject
	deleteGCSObjectFn = deleteGCSObject
	gcsObjectExistsFn = gcsObjectExists
)

// Rename is a single source→destination object rename within one bucket.
type Rename struct{ Src, Dst string }

// RenameGCSObject copies srcObject to dstObject within the same bucket
// (server-side, no download) and deletes the source. Per design #842 §4d:
//
//   - Copy failure is FATAL: any partial destination is best-effort removed so
//     no orphaned destination is left behind, the source is left intact, and a
//     fatal error naming both src and dst is returned.
//   - Delete failure is NON-FATAL: the desired object (dst) exists and is valid,
//     so a warning is logged and nil is returned — a leftover source object is
//     cosmetic, not a data error.
//   - A pre-existing destination is overwritten with a warning (§4e). Server-side
//     copy overwrites by default; the warning just makes it observable.
//
// A src == dst rename is a no-op and returns nil.
//
// Latency note: a same-bucket, same-region copy is a metadata operation (fast);
// cross-region or very large objects add copy latency proportional to size. This
// runs after generation and before the tool returns, so the client sees it as
// added tool latency.
func RenameGCSObject(ctx context.Context, bucket, srcObject, dstObject string) error {
	if bucket == "" {
		return fmt.Errorf("RenameGCSObject: bucket must not be empty")
	}
	if srcObject == "" || dstObject == "" {
		return fmt.Errorf("RenameGCSObject: src (%q) and dst (%q) must both be non-empty", srcObject, dstObject)
	}
	if srcObject == dstObject {
		return nil // nothing to do
	}

	// Collision (§4e): overwrite, but make it observable. A best-effort existence
	// probe only drives the warning log — it never blocks the rename.
	if exists, existsErr := gcsObjectExistsFn(ctx, bucket, dstObject); existsErr != nil {
		log.Printf("RenameGCSObject: could not check whether destination gs://%s/%s exists (continuing): %v", bucket, dstObject, existsErr)
	} else if exists {
		log.Printf("RenameGCSObject: destination gs://%s/%s already exists; overwriting", bucket, dstObject)
	}

	if err := copyGCSObjectFn(ctx, bucket, srcObject, dstObject); err != nil {
		// Copy failed. Best-effort remove any partial destination so no orphan is
		// left, leave the source untouched, and return a fatal error.
		if delErr := deleteGCSObjectFn(ctx, bucket, dstObject); delErr != nil && !errors.Is(delErr, storage.ErrObjectNotExist) {
			log.Printf("RenameGCSObject: copy gs://%s/%s -> gs://%s/%s failed and cleanup of any partial destination also failed: %v", bucket, srcObject, bucket, dstObject, delErr)
		}
		return fmt.Errorf("RenameGCSObject: copy gs://%s/%s -> gs://%s/%s failed: %w", bucket, srcObject, bucket, dstObject, err)
	}

	// Copy succeeded; the desired object now exists. Deleting the source is
	// housekeeping — a failure leaves a cosmetic leftover, not a data error.
	if err := deleteGCSObjectFn(ctx, bucket, srcObject); err != nil {
		log.Printf("RenameGCSObject: could not remove API-original gs://%s/%s after successful copy to %s (non-fatal): %v", bucket, srcObject, dstObject, err)
	}
	return nil
}

// RenameGCSObjects renames a batch of objects within one bucket, sequentially.
// On the first copy failure it stops and returns the destination names already
// renamed plus a fatal error that names the source object left behind. Already
// renamed objects are valid outputs the client asked for and are NOT rolled back
// (design #842 §4d) — rolling back would delete correctly-named media. On full
// success every source object has been removed.
func RenameGCSObjects(ctx context.Context, bucket string, renames []Rename) (renamed []string, err error) {
	for _, r := range renames {
		if rErr := RenameGCSObject(ctx, bucket, r.Src, r.Dst); rErr != nil {
			return renamed, fmt.Errorf("RenameGCSObjects: renamed %d of %d before failing on gs://%s/%s (source left in place): %w", len(renamed), len(renames), bucket, r.Src, rErr)
		}
		renamed = append(renamed, r.Dst)
	}
	return renamed, nil
}

// copyGCSObject performs a server-side copy of srcObject to dstObject within the
// same bucket (no download). GCS object copy is atomic per object: the
// destination either exists fully or not at all.
func copyGCSObject(ctx context.Context, bucket, srcObject, dstObject string) error {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return fmt.Errorf("storage.NewClient: %w", err)
	}
	defer func() { _ = client.Close() }()

	src := client.Bucket(bucket).Object(srcObject)
	dst := client.Bucket(bucket).Object(dstObject)
	if _, err := dst.CopierFrom(src).Run(ctx); err != nil {
		return fmt.Errorf("CopierFrom(%q).Run to %q: %w", srcObject, dstObject, err)
	}
	return nil
}

// deleteGCSObject deletes a single object.
func deleteGCSObject(ctx context.Context, bucket, object string) error {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return fmt.Errorf("storage.NewClient: %w", err)
	}
	defer func() { _ = client.Close() }()

	if err := client.Bucket(bucket).Object(object).Delete(ctx); err != nil {
		return fmt.Errorf("Object(%q).Delete: %w", object, err)
	}
	return nil
}

// gcsObjectExists reports whether an object exists. A not-found result is
// returned as (false, nil); any other error is surfaced to the caller.
func gcsObjectExists(ctx context.Context, bucket, object string) (bool, error) {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return false, fmt.Errorf("storage.NewClient: %w", err)
	}
	defer func() { _ = client.Close() }()

	_, err = client.Bucket(bucket).Object(object).Attrs(ctx)
	if errors.Is(err, storage.ErrObjectNotExist) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}
