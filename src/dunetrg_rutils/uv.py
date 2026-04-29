import ROOT
from typing import Optional


class UniqueValueFinder:
    """
    Find unique values of scalar or vector/RVec branches in an RDataFrame.

    Works for any hashable C++ type ROOT can read (integers, strings, etc.).
    Uses ForeachSlot under the hood, so it's thread-safe with EnableImplicitMT.

    Example
    -------
    >>> df = ROOT.RDataFrame("tree", files)
    >>> finder = UniqueValueFinder(df)
    >>> pdgs  = finder.find("pdg")               # auto-detects type
    >>> names = finder.find("generator_name")
    >>> all_unique = finder.find_many(["pdg", "generator_name"])
    """

    # Map ROOT's short aliases to canonical C++ type names
    _CANONICAL = {
        "Int_t":      "int",
        "UInt_t":     "unsigned int",
        "Long_t":     "long",
        "Long64_t":   "long long",
        "ULong_t":    "unsigned long",
        "ULong64_t":  "unsigned long long",
        "Short_t":    "short",
        "UShort_t":   "unsigned short",
        "string":     "std::string",
    }

    _VECTOR_PREFIXES = (
        "ROOT::VecOps::RVec<",
        "ROOT::RVec<",
        "std::vector<",
        "vector<",
    )

    # Class-level flag: C++ helpers declared only once per Python process
    _cpp_declared = False

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #
    def __init__(self, df, enable_mt: bool = True):
        if enable_mt and not ROOT.IsImplicitMTEnabled():
            ROOT.EnableImplicitMT()

        self._df = df
        self._node = ROOT.RDF.AsRNode(df)
        self._ensure_cpp_declared()

    @classmethod
    def _ensure_cpp_declared(cls) -> None:
        """Declare the C++ helper once per process."""
        if cls._cpp_declared:
            return

        ROOT.gInterpreter.Declare(r"""
        #ifndef UNIQUE_VALUE_FINDER_DEFINED
        #define UNIQUE_VALUE_FINDER_DEFINED

        #include <set>
        #include <vector>
        #include <string>
        #include <memory>
        #include "ROOT/RVec.hxx"
        #include "ROOT/RDataFrame.hxx"

        namespace unique_value_finder {

        template <typename T>
        class Collector {
        public:
            explicit Collector(unsigned int nslots) : per_slot_(nslots) {}

            void accumulate(unsigned int slot, const T& v) {
                per_slot_[slot].insert(v);
            }
            void accumulate(unsigned int slot, const ROOT::RVec<T>& vs) {
                for (const auto& v : vs) per_slot_[slot].insert(v);
            }

            std::set<T> merge() const {
                std::set<T> out;
                for (const auto& s : per_slot_) out.insert(s.begin(), s.end());
                return out;
            }
        private:
            std::vector<std::set<T>> per_slot_;
        };

        template <typename T, bool IsVector>
        std::set<T> collect(ROOT::RDF::RNode df, const std::string& branch) {
            auto collector = std::make_shared<Collector<T>>(df.GetNSlots());

            if constexpr (IsVector) {
                df.ForeachSlot(
                    [collector](unsigned int slot, const ROOT::RVec<T>& vs) {
                        collector->accumulate(slot, vs);
                    }, {branch});
            } else {
                df.ForeachSlot(
                    [collector](unsigned int slot, const T& v) {
                        collector->accumulate(slot, v);
                    }, {branch});
            }
            return collector->merge();
        }

        } // namespace unique_value_finder
        #endif
        """)
        cls._cpp_declared = True

    # --------------------------------------------------------------------- #
    # Type parsing
    # --------------------------------------------------------------------- #
    @classmethod
    def _canonical(cls, t: str) -> str:
        return cls._CANONICAL.get(t, t)

    @classmethod
    def _parse_column_type(cls, col_type: str) -> tuple[str, bool]:
        """Return (inner_type, is_vector) for a ROOT column type string."""
        t = col_type.strip()
        for prefix in cls._VECTOR_PREFIXES:
            if t.startswith(prefix) and t.endswith(">"):
                return cls._canonical(t[len(prefix):-1].strip()), True
        return cls._canonical(t), False

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def find(self, branch_name: str, dtype: Optional[str] = None) -> set:
        """
        Return the set of unique values in `branch_name`.

        Parameters
        ----------
        branch_name : str
            Name of the branch.
        dtype : str, optional
            Override for the inner C++ type (e.g. 'int', 'std::string').
            If omitted, inferred from the branch metadata.
        """
        if dtype is None:
            inner, is_vec = self._parse_column_type(
                self._df.GetColumnType(branch_name)
            )
        else:
            inner = self._canonical(dtype)
            # Treat explicit dtype as scalar unless it starts with a vector prefix
            inner, is_vec = self._parse_column_type(inner) if any(
                inner.startswith(p) for p in self._VECTOR_PREFIXES
            ) else (inner, False)

        collect = ROOT.unique_value_finder.collect[
            inner, "true" if is_vec else "false"
        ]
        return set(collect(self._node, branch_name))

    def find_many(self, branch_names: list[str]) -> dict[str, set]:
        """Find unique values for multiple branches. Returns a dict."""
        return {name: self.find(name) for name in branch_names}

    def column_type(self, branch_name: str) -> tuple[str, bool]:
        """Return the parsed (inner_type, is_vector) tuple for a branch."""
        return self._parse_column_type(self._df.GetColumnType(branch_name))

    # --------------------------------------------------------------------- #
    # Pythonic niceties
    # --------------------------------------------------------------------- #
    def __call__(self, branch_name: str, dtype: Optional[str] = None) -> set:
        """Shortcut so `finder("pdg")` works like `finder.find("pdg")`."""
        return self.find(branch_name, dtype)

    def __repr__(self) -> str:
        return f"<UniqueValueFinder on {type(self._df).__name__}>"