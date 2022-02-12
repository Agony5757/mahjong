#ifndef PROFILER_H
#define PROFILER_H
#include <chrono>
#include <map>
#include <type_traits>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include "fmt/core.h"

constexpr double nanosec = 1;
constexpr double microsec = nanosec / 1e3;
constexpr double millisec = microsec / 1e3;
constexpr double sec = millisec / 1e3;
constexpr double minute = sec / 60;
constexpr double hour = minute / 60;
constexpr double day = hour / 24;

template<typename T>
struct _remove_cvref {
    using type = std::remove_cv_t<std::remove_reference_t<T>>;
};

template<typename T>
using _remove_cvref_t = typename _remove_cvref<T>::type;

template<typename Ty>
void* to_voidptr(Ty ptr) {
    using T_ptr_t = _remove_cvref_t<Ty>;
    using T = _remove_cvref_t<std::remove_pointer_t<T_ptr_t>>;
    using clear_pointer_type = T*;
    return reinterpret_cast<void*>(const_cast<clear_pointer_type>(ptr));
}

template<typename KeyTy, typename ValTy>
void map2vec(std::vector<std::pair<void*, void*>>& vec, const std::map<KeyTy, ValTy>& map1) {
    vec.clear();
    vec.reserve(map1.size());
    for (const auto& item : map1) {
        void* keyptr = to_voidptr(&(item.first));
        void* valptr = to_voidptr(&(item.second));
        vec.push_back({ keyptr, valptr });
    }
}

struct timer {
    std::chrono::time_point<std::chrono::steady_clock> startpoint;
    inline timer() {
        startpoint = std::chrono::steady_clock::now();
    }
    inline double get(double unit) {
        std::chrono::nanoseconds m = std::chrono::steady_clock::now() - startpoint;
        return std::chrono::duration_cast<std::chrono::nanoseconds>(m).count() * unit;
    }
};

struct profile {
    size_t ncalls = 0;
    double time = 0;
    std::vector<timer> timers;
    size_t max_depth = 100;
    profile() { enter(); }
    inline void enter() 
    {
        if (timers.size() == max_depth)
            throw std::runtime_error("Exceed max depth.");
        timers.push_back(timer());
        ncalls++;
    }
    inline void exit()
    {
        if (timers.size() == 0)
            throw std::runtime_error("Why profiler has 0 timer?");
        time += timers.back().get(millisec);
        timers.pop_back();
    }
};

struct profiler {
    static std::map<std::string, profile*> profiles;
    static bool on;
#ifndef Profiling
    template<typename ...Ty> profiler(const Ty... args) {};
    template<typename ...Ty> static void print_profiles() {};
#else
    std::string current_identifier;
    profile* current_profile;

    inline profiler(std::string function_identifier)
    {
        if (!on) { return; }
        if (function_identifier.size() > 25) {
            current_identifier.assign(function_identifier.begin(), function_identifier.begin() + 15);
            current_identifier += "...";
        }
        else {
            current_identifier = function_identifier;
        }
        auto iter = profiles.find(function_identifier);
        if (iter == profiles.end()) {
            current_profile = new profile();
            profiles.insert({ current_identifier, current_profile });
        }
        else {
            current_profile = iter->second;
            current_profile->enter();
        }
    }

    inline ~profiler()
    {
        if (!on) { return; }
        current_profile->exit();
    }

    inline static void init_profiler() 
    {
        profiles.clear();
    }

    inline static void close_profiler() 
    {
        profiler::on = false;
    }

    inline static void start_profiler() 
    {
        profiler::on = true;
    }

    inline static double get_time(std::string profilename) 
    {
        auto iter = profiles.find(profilename);
        if (iter == profiles.end()) return -1.0;
        else return iter->second->time;
    }

    inline static size_t get_ncalls(std::string profilename) 
    {
        auto iter = profiles.find(profilename);
        if (iter == profiles.end()) return -1;
        else return iter->second->ncalls;
    }

    inline static std::string get_all_profiles() 
    {
        if (profiles.empty()) {
            return "No profiles.";
        }
        std::string ret;
        for (auto profile : profiles) {
            ret += fmt::format("[{:^28s}] Calls = {:^3d} Time = {:^4f} ms\n",
                profile.first, profile.second->ncalls, profile.second->time);
        }
        return ret;
    }
    inline static std::string get_all_profiles_v2()
    {
        std::string ret;
        if (profiles.empty()) {
            return "No profiles.";
        }
        else {
            ret += fmt::format("Item: {}\n", profiles.size());
        }
        std::vector<std::pair<void*, void*>> profvec;
        map2vec(profvec, profiles);

        auto get_time = [](const std::pair<void*, void*>& item) {
            return (*static_cast<profile**>(item.second))->time;
        };
        auto get_name = [](const std::pair<void*, void*>& item) {
            return (*static_cast<std::string*>(item.first));
        };
        auto get_profile = [](const std::pair<void*, void*>& item) {
            return (*static_cast<profile**>(item.second));
        };

        std::sort(profvec.begin(), profvec.end(), [&get_time](
            const std::pair<void*, void*>& item1,
            const std::pair<void*, void*>& item2)
            {
                return get_time(item1) > get_time(item2);
            }
        );

        for (const auto& profile : profvec) {
            ret += fmt::format("[{:^28s}] Calls = {:^3d} Time = {:^4f} ms\n",
                get_name(profile), get_profile(profile)->ncalls, get_profile(profile)->time);
        }
        return ret;
    }
    inline static void print_profiles() {
        std::cout << get_all_profiles_v2();
    }
#endif

};
#define FunctionProfiler volatile profiler _profilehelper_(__FUNCTION__)
#endif